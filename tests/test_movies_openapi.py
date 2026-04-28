from app.main import app


def test_admin_movie_create_openapi_uses_pydantic_json_schema():
    schema = app.openapi()
    create_operation = schema["paths"]["/v1/admin/movies/"]["post"]
    update_operation = schema["paths"]["/v1/admin/movies/{movie_id}"]["patch"]
    poster_operation = schema["paths"]["/v1/admin/movies/{movie_id}/poster"]["post"]
    series_create_operation = schema["paths"]["/v1/admin/series/"]["post"]

    assert "requestBody" in create_operation
    create_content = create_operation["requestBody"]["content"]
    update_content = update_operation["requestBody"]["content"]
    poster_content = poster_operation["requestBody"]["content"]

    assert list(create_content) == ["application/json"]
    assert list(update_content) == ["application/json"]
    assert list(poster_content) == ["multipart/form-data"]
    assert create_content["application/json"]["schema"]["$ref"] == "#/components/schemas/MovieCreate"
    assert update_content["application/json"]["schema"]["$ref"] == "#/components/schemas/MovieUpdate"

    series_content = series_create_operation["requestBody"]["content"]
    series_json_schema = series_content["application/json"]["schema"]
    series_multipart_schema = series_content["multipart/form-data"]["schema"]

    assert "episodes" in series_json_schema["properties"]
    assert "seasons_count" in series_multipart_schema["properties"]
