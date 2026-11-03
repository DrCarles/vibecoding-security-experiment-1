import io

from PIL import Image

from .conftest import register


def png_bytes(size=(64, 48), color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


# --- registration & auth -------------------------------------------------------


def test_register_captures_profile_and_signs_in(client):
    r = register(client, username="Alice_1", email="ALICE@Example.com")
    assert r.status_code == 201, r.text
    me = r.json()
    assert me["username"] == "alice_1"
    assert me["email"] == "alice@example.com"
    assert me["display_name"] == "Alice Liddell"
    assert (me["first_name"], me["last_name"], me["age"]) == ("Alice", "Liddell", 30)
    assert me["address"].startswith("1 Rabbit")
    assert "password_hash" not in me

    assert client.get("/api/users/me").json()["id"] == me["id"]


def test_register_validation(client):
    assert register(client, age=12).status_code == 422
    assert register(client, password="short1").status_code == 422
    assert register(client, password="nodigitshere").status_code == 422
    assert register(client, username="no spaces").status_code == 422
    assert register(client, username="me").status_code == 422
    assert register(client, address="  ").status_code == 422
    assert register(client, first_name="").status_code == 422


def test_register_duplicates(client, make_client):
    assert register(client).status_code == 201
    other = make_client()
    assert register(other, email="new@example.com").status_code == 409
    assert register(other, username="bob", email="ALICE@example.com").status_code == 409


def test_login_logout(client, make_client):
    register(client)
    anon = make_client()
    assert anon.get("/api/users/me").status_code == 401
    assert anon.post("/api/auth/login", json={"login": "alice", "password": "wrong1234"}).status_code == 401
    assert anon.post("/api/auth/login", json={"login": "ghost", "password": "wrong1234"}).status_code == 401
    assert anon.post("/api/auth/login", json={"login": "Alice@Example.com", "password": "s3cretpass"}).status_code == 200
    assert anon.get("/api/users/me").status_code == 200
    assert anon.post("/api/auth/logout").status_code == 204
    assert anon.get("/api/users/me").status_code == 401


def test_csrf_header_required(make_client):
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as bare:
        r = bare.post("/api/auth/login", json={"login": "a", "password": "b"})
        assert r.status_code == 403


# --- posts ---------------------------------------------------------------------


def test_create_text_and_image_posts(client):
    register(client)
    r = client.post("/api/posts", data={"body": "  hello world  "})
    assert r.status_code == 201, r.text
    assert r.json()["body"] == "hello world"
    assert r.json()["author"]["username"] == "alice"

    r = client.post("/api/posts", data={"body": ""}, files={"image": ("pic.png", png_bytes(), "image/png")})
    assert r.status_code == 201, r.text
    url = r.json()["image_url"]
    assert url.startswith("/media/posts/") and url.endswith(".webp")
    img = client.get(url)
    assert img.status_code == 200
    assert Image.open(io.BytesIO(img.content)).format == "WEBP"


def test_post_validation(client, make_client):
    assert make_client().post("/api/posts", data={"body": "hi"}).status_code == 401
    register(client)
    assert client.post("/api/posts", data={"body": "   "}).status_code == 422
    assert client.post("/api/posts", data={"body": "x" * 281}).status_code == 422
    assert client.post("/api/posts", data={"body": "x" * 280}).status_code == 201
    bad = client.post("/api/posts", data={"body": "a"}, files={"image": ("x.png", b"not an image", "image/png")})
    assert bad.status_code == 400


def test_feed_pagination_and_author_filter(client, make_client):
    register(client)
    for i in range(5):
        client.post("/api/posts", data={"body": f"alice {i}"})
    bob = make_client()
    register(bob, username="bob")
    bob.post("/api/posts", data={"body": "bob 0"})

    anon = make_client()
    page1 = anon.get("/api/posts", params={"limit": 4}).json()
    assert [p["body"] for p in page1["items"]] == ["bob 0", "alice 4", "alice 3", "alice 2"]
    page2 = anon.get("/api/posts", params={"limit": 4, "before": page1["next_cursor"]}).json()
    assert [p["body"] for p in page2["items"]] == ["alice 1", "alice 0"]
    assert page2["next_cursor"] is None

    only_bob = anon.get("/api/posts", params={"author": "BOB"}).json()
    assert [p["body"] for p in only_bob["items"]] == ["bob 0"]
    assert anon.get("/api/posts", params={"author": "nobody"}).status_code == 404


def test_delete_only_own_posts(client, make_client):
    register(client)
    post_id = client.post("/api/posts", data={"body": "mine"}).json()["id"]
    bob = make_client()
    register(bob, username="bob")
    assert bob.delete(f"/api/posts/{post_id}").status_code == 403
    assert client.delete(f"/api/posts/{post_id}").status_code == 204
    assert client.delete(f"/api/posts/{post_id}").status_code == 404


# --- profile management --------------------------------------------------------


def test_update_display_name(client):
    register(client)
    r = client.patch("/api/users/me", json={"display_name": "  Mad Hatter  "})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Mad Hatter"
    assert client.patch("/api/users/me", json={"display_name": ""}).status_code == 422
    assert client.patch("/api/users/me", json={"display_name": "x" * 51}).status_code == 422
    assert client.get("/api/users/alice").json()["display_name"] == "Mad Hatter"


def test_avatar_upload_and_remove(client):
    register(client)
    r = client.put("/api/users/me/avatar", files={"file": ("a.png", png_bytes((900, 500)), "image/png")})
    assert r.status_code == 200, r.text
    url = r.json()["avatar_url"]
    img = Image.open(io.BytesIO(client.get(url).content))
    assert img.size == (400, 400)

    r = client.put("/api/users/me/avatar", files={"file": ("b.png", png_bytes(), "image/png")})
    assert client.get(url).status_code == 404  # old file cleaned up
    assert client.delete("/api/users/me/avatar").json()["avatar_url"] is None
    assert client.get(r.json()["avatar_url"]).status_code == 404


def test_password_change_revokes_other_sessions(client, make_client):
    register(client)
    other = make_client()
    other.post("/api/auth/login", json={"login": "alice", "password": "s3cretpass"})
    assert other.get("/api/users/me").status_code == 200

    bad = client.put("/api/users/me/password", json={"current_password": "nope", "new_password": "n3wpassword"})
    assert bad.status_code == 400
    weak = client.put("/api/users/me/password", json={"current_password": "s3cretpass", "new_password": "weak"})
    assert weak.status_code == 422

    ok = client.put("/api/users/me/password", json={"current_password": "s3cretpass", "new_password": "n3wpassword"})
    assert ok.status_code == 204
    assert client.get("/api/users/me").status_code == 200  # this session gets a fresh cookie
    assert other.get("/api/users/me").status_code == 401  # others are signed out

    fresh = make_client()
    assert fresh.post("/api/auth/login", json={"login": "alice", "password": "s3cretpass"}).status_code == 401
    assert fresh.post("/api/auth/login", json={"login": "alice", "password": "n3wpassword"}).status_code == 200


def test_public_profile_hides_private_fields(client, make_client):
    register(client)
    public = make_client().get("/api/users/alice").json()
    for private in ("email", "first_name", "last_name", "age", "address"):
        assert private not in public
