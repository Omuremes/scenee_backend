from app.main import app


def test_admin_movie_create_openapi_exposes_request_body_schema():
    schema = app.openapi()
    create_operation = schema["paths"]["/v1/admin/movies/"]["post"]

    assert "requestBody" in create_operation
    content = create_operation["requestBody"]["content"]
    assert "application/json" in content
    assert "multipart/form-data" in content

    json_schema = content["application/json"]["schema"]
    multipart_schema = content["multipart/form-data"]["schema"]

    assert "properties" in json_schema
    assert "name" in json_schema["properties"]
    assert "poster" in json_schema["properties"]
    assert "properties" in multipart_schema
    assert "poster" in multipart_schema["properties"]
