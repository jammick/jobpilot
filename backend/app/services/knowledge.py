import json
import logging
import math
from pathlib import Path

import yaml
from fastapi import HTTPException, UploadFile
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import CompetencyRule, KnowledgeBase, KnowledgeChunk, KnowledgeDocument, RoleProfile, Skill, SkillAlias
from app.schemas.contracts import KnowledgeManifestInput
from app.services.documents import extract_text

logger = logging.getLogger(__name__)


def _embeddings() -> OpenAIEmbeddings | None:
    settings = get_settings()
    api_key = settings.embedding_api_key or settings.openai_api_key
    base_url = settings.embedding_base_url or settings.openai_base_url
    if not api_key:
        return None
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=api_key,
        base_url=base_url,
        max_retries=1,
    )


def embed_texts(texts: list[str]) -> list[list[float] | None]:
    if not texts:
        return []
    client = _embeddings()
    if not client:
        return [None] * len(texts)
    try:
        vectors = client.embed_documents(texts)
        expected = get_settings().embedding_dimension
        if any(len(vector) != expected for vector in vectors):
            logger.error("embedding dimension mismatch expected=%s", expected)
            return [None] * len(texts)
        return vectors
    except Exception:
        # Indexing must not make uploaded private source files unavailable.
        logger.exception("document embedding failed")
        return [None] * len(texts)


def embed_query(text: str) -> list[float] | None:
    client = _embeddings()
    if not client:
        return None
    try:
        vector = client.embed_query(text)
        if len(vector) != get_settings().embedding_dimension:
            logger.error(
                "query embedding dimension mismatch expected=%s actual=%s",
                get_settings().embedding_dimension,
                len(vector),
            )
            return None
        return vector
    except Exception:
        logger.exception("query embedding failed")
        return None


def _cosine(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def search_knowledge_chunks(db: Session, base_id: str, query: str, limit: int = 5) -> tuple[str, list[dict]]:
    vector = embed_query(query)
    terms = [term.lower() for term in query.split() if term.strip()]
    if vector and db.get_bind().dialect.name == "postgresql":
        distance = KnowledgeChunk.embedding.cosine_distance(vector)
        semantic_rows = (
            db.query(KnowledgeChunk)
            .filter(
                KnowledgeChunk.knowledge_base_id == base_id,
                KnowledgeChunk.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(max(limit * 5, 25))
            .all()
        )
        lexical_filter = or_(*(func.lower(KnowledgeChunk.content).contains(term) for term in terms)) if terms else None
        lexical_query = db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_base_id == base_id)
        if lexical_filter is not None:
            lexical_query = lexical_query.filter(lexical_filter)
        lexical_rows = lexical_query.limit(250).all()
        chunks = list({chunk.id: chunk for chunk in [*semantic_rows, *lexical_rows]}.values())
    else:
        # SQLite is intentionally a small local-development fallback.
        chunks = db.query(KnowledgeChunk).filter_by(knowledge_base_id=base_id).all()
    ranked = []
    for chunk in chunks:
        lexical = sum(term in chunk.content.lower() for term in terms)
        semantic = _cosine(vector, chunk.embedding)
        if lexical or semantic > 0:
            ranked.append((lexical + semantic, chunk, lexical, semantic))
    ranked.sort(key=lambda item: item[0], reverse=True)
    mode = "hybrid" if vector else "keyword"
    return mode, [{"id": chunk.id, "content": chunk.content[:500], "score": round(score, 4), "keyword_hits": lexical, "semantic_score": round(semantic, 4), "vector_indexed": chunk.embedding is not None} for score, chunk, lexical, semantic in ranked[:limit]]


def parse_manifest(raw: bytes, filename: str) -> KnowledgeManifestInput:
    suffix = Path(filename or "manifest.json").suffix.lower()
    try:
        payload = yaml.safe_load(raw) if suffix in {".yaml", ".yml"} else json.loads(raw)
    except (json.JSONDecodeError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise HTTPException(422, "知识包无法解析；请上传 JSON 或 YAML") from exc
    return KnowledgeManifestInput.model_validate(payload)


def validate_manifest(manifest: KnowledgeManifestInput) -> list[str]:
    errors: list[str] = []
    names = {skill.name.lower() for skill in manifest.skills}
    aliases: set[str] = set()
    for skill in manifest.skills:
        for alias in [skill.name, *skill.aliases]:
            key = alias.strip().lower()
            if not key:
                errors.append(f"技能 {skill.name} 存在空别名")
            elif key in aliases:
                errors.append(f"技能别名重复：{alias}")
            aliases.add(key)
    for rule in manifest.rules:
        unknown = [skill for skill in rule.skills if skill.lower() not in names]
        if unknown:
            errors.append(f"能力项 {rule.name} 引用了未定义技能：{', '.join(unknown)}")
    if not any(rule.required for rule in manifest.rules):
        errors.append("至少需要一个硬门槛能力项")
    return errors


async def import_knowledge_base(
    db: Session, user_id: str, manifest_file: UploadFile, documents: list[UploadFile],
) -> KnowledgeBase:
    raw = await manifest_file.read()
    manifest = parse_manifest(raw, manifest_file.filename or "manifest.json")
    validation = validate_manifest(manifest)
    if validation:
        raise HTTPException(422, {"message": "知识包校验失败", "errors": validation})
    settings = get_settings()
    base = KnowledgeBase(
        user_id=user_id,
        name=manifest.name,
        role_key=manifest.role_key,
        version=manifest.version,
        status="draft",
        embedding_model=settings.embedding_model,
        manifest=manifest.model_dump(),
    )
    db.add(base)
    db.flush()

    profile = RoleProfile(knowledge_base_id=base.id, role_key=manifest.role_key, name=manifest.role_name)
    db.add(profile)
    db.flush()
    skills: dict[str, Skill] = {}
    for item in manifest.skills:
        skill = Skill(knowledge_base_id=base.id, canonical_name=item.name, category=item.category)
        db.add(skill)
        db.flush()
        skills[item.name.lower()] = skill
        for alias in {item.name, *item.aliases}:
            db.add(SkillAlias(skill_id=skill.id, alias=alias.strip().lower()))
    for rule in manifest.rules:
        db.add(
            CompetencyRule(
                role_profile_id=profile.id,
                rule_key=rule.key,
                name=rule.name,
                weight=rule.weight,
                required=rule.required,
                skill_names=[skills[name.lower()].canonical_name for name in rule.skills],
                description=rule.description,
            )
        )

    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
    for upload in documents:
        suffix = Path(upload.filename or "").suffix.lower()
        raw_doc = await upload.read()
        if not raw_doc:
            continue
        try:
            content = extract_text(raw_doc, suffix)
        except HTTPException:
            raise
        if len(content) < 30:
            raise HTTPException(422, f"知识资料 {upload.filename} 未提取到足够文本")
        document = KnowledgeDocument(knowledge_base_id=base.id, original_name=upload.filename or "document", content=content)
        db.add(document)
        db.flush()
        chunks = splitter.split_text(content)
        vectors = embed_texts(chunks)
        for chunk, vector in zip(chunks, vectors):
            db.add(KnowledgeChunk(knowledge_base_id=base.id, document_id=document.id, content=chunk, embedding=vector))
    db.commit()
    db.refresh(base)
    return base


def detail(base: KnowledgeBase, document_count: int = 0) -> dict:
    manifest = KnowledgeManifestInput.model_validate(base.manifest)
    return {
        "id": base.id,
        "name": base.name,
        "role_key": base.role_key,
        "version": base.version,
        "status": base.status,
        "embedding_model": base.embedding_model,
        "created_at": base.created_at,
        "manifest": base.manifest,
        "document_count": document_count,
        "validation": validate_manifest(manifest),
    }


def published_profile(
    db: Session,
    user_id: str,
    role_profile_id: str | None,
    *,
    allow_archived: bool = False,
) -> tuple[KnowledgeBase, RoleProfile, list[CompetencyRule]]:
    statuses = ["published", "archived"] if allow_archived and role_profile_id else ["published"]
    # Published role profiles are developer-owned global product knowledge.
    # The caller's user_id scopes resumes and analyses, not the shared rules.
    query = db.query(RoleProfile, KnowledgeBase).join(KnowledgeBase, RoleProfile.knowledge_base_id == KnowledgeBase.id).filter(KnowledgeBase.status.in_(statuses))
    if role_profile_id:
        query = query.filter(RoleProfile.id == role_profile_id)
    item = query.order_by(KnowledgeBase.created_at.desc()).first()
    if not item:
        raise HTTPException(409, "请先在知识中心导入并发布 AI 产品经理知识包")
    profile, base = item
    rules = db.query(CompetencyRule).filter_by(role_profile_id=profile.id).order_by(CompetencyRule.rule_key).all()
    return base, profile, rules


def normalize_aliases(db: Session, base_id: str) -> dict[str, str]:
    rows = db.query(SkillAlias.alias, Skill.canonical_name).join(Skill, SkillAlias.skill_id == Skill.id).filter(Skill.knowledge_base_id == base_id).all()
    return {alias.lower(): canonical for alias, canonical in rows}


def publish_knowledge_base(db: Session, user_id: str, base: KnowledgeBase) -> KnowledgeBase:
    errors = validate_manifest(KnowledgeManifestInput.model_validate(base.manifest))
    if errors:
        raise HTTPException(422, {"message": "知识包无法发布", "errors": errors})
    db.query(KnowledgeBase).filter(KnowledgeBase.user_id == user_id, KnowledgeBase.role_key == base.role_key, KnowledgeBase.status == "published").update({"status": "archived"})
    base.status = "published"
    db.commit()
    db.refresh(base)
    return base
