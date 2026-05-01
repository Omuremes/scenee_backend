from app.main import app


def test_admin_movie_create_openapi_uses_pydantic_json_schema():
    schema = app.openapi()
    create_operation = schema["paths"]["/v1/admin/movies/"]["post"]
    update_operation = schema["paths"]["/v1/admin/movies/{movie_id}"]["patch"]
    poster_operation = schema["paths"]["/v1/admin/movies/{movie_id}/poster"]["post"]
    serial_create_operation = schema["paths"]["/v1/admin/serials/"]["post"]

    assert "requestBody" in create_operation
    create_content = create_operation["requestBody"]["content"]
    update_content = update_operation["requestBody"]["content"]
    poster_content = poster_operation["requestBody"]["content"]

    assert list(create_content) == ["application/json"]
    assert list(update_content) == ["application/json"]
    assert list(poster_content) == ["multipart/form-data"]
    assert create_content["application/json"]["schema"]["$ref"] == "#/components/schemas/MovieCreate"
    assert update_content["application/json"]["schema"]["$ref"] == "#/components/schemas/MovieUpdate"

    serial_content = serial_create_operation["requestBody"]["content"]
    serial_json_schema = serial_content["application/json"]["schema"]

    assert list(serial_content) == ["application/json"]
    assert serial_json_schema["$ref"] == "#/components/schemas/SerialCreate"
