from typing import Optional
import pytest
from pydantic import Field, BaseModel
from beanie import Document, init_beanie, Indexed

class DocumentWithSerializationAlias(Document):
    test_field: str = Field(serialization_alias="aliasedField")
    
    class Settings:
        name = "doc_with_alias"

class DocumentWithIndexAndAlias(Document):
    test_field: Indexed(str) = Field(serialization_alias="aliasedIndexField")

    class Settings:
        name = "doc_with_index_alias"

async def test_serialization_alias_persistence(db):
    await init_beanie(database=db, document_models=[DocumentWithSerializationAlias])
    
    doc = DocumentWithSerializationAlias(test_field="test")
    await doc.save()
    
    # Check in DB
    raw_doc = await db["doc_with_alias"].find_one({"_id": doc.id})
    assert "aliasedField" in raw_doc
    assert raw_doc["aliasedField"] == "test"
    assert "test_field" not in raw_doc

async def test_serialization_alias_query(db):
    await init_beanie(database=db, document_models=[DocumentWithSerializationAlias])
    
    doc = DocumentWithSerializationAlias(test_field="query_test")
    await doc.save()
    
    # Query using model field (should map to alias)
    found = await DocumentWithSerializationAlias.find_one(DocumentWithSerializationAlias.test_field == "query_test")
    assert found is not None
    assert found.test_field == "query_test"

async def test_index_creation_with_alias(db):
    await init_beanie(database=db, document_models=[DocumentWithIndexAndAlias])
    
    collection = DocumentWithIndexAndAlias.get_motor_collection()
    index_info = await collection.index_information()
    
    # Check for index on "aliasedIndexField"
    found = False
    for name, info in index_info.items():
        if "key" in info and info["key"][0][0] == "aliasedIndexField":
            found = True
            break
    
    assert found

async def test_index_recreation_on_alias_change(db):
    # 1. Init with alias "alias1"
    class DocV1(Document):
        field: Indexed(str) = Field(serialization_alias="alias1")
        class Settings:
            name = "doc_alias_change"
    
    await init_beanie(database=db, document_models=[DocV1])
    
    collection = db["doc_alias_change"]
    indexes = await collection.index_information()
    assert any(k[0] == "alias1" for i in indexes.values() for k in i["key"])

    # 2. Init with alias "alias2" (simulate code change)
    # We reuse the same collection name
    class DocV2(Document):
        field: Indexed(str) = Field(serialization_alias="alias2")
        class Settings:
            name = "doc_alias_change"

    # This should trigger the automatic drop/recreate logic because index changed
    await init_beanie(database=db, document_models=[DocV2])
    
    indexes = await collection.index_information()
    # Should have alias2, and NOT alias1
    assert any(k[0] == "alias2" for i in indexes.values() for k in i["key"])
    assert not any(k[0] == "alias1" for i in indexes.values() for k in i["key"])

