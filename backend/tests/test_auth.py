"""인증 — 요청 주체 판정과 제공자 응답 정규화.

DB를 안 탄다. 여기서 잡고 싶은 건 두 가지다:
  ① 토큰이 없거나 깨졌을 때 **어디로 떨어지는가** — 폴백이 무너지면 로그인
     하나 붙였다가 기존 화면이 전부 401이 된다.
  ② 제공자 응답 모양 차이(구글 평면 / 네이버 response 래핑).
"""
import uuid

import pytest
from fastapi import HTTPException

from app.core.deps import DEV_USER_ID, get_current_user_id
from app.core.security import create_access_token, decode_access_token
from app.features.auth import oauth


class FakeDB:
    """users 테이블 대역. `known`에 있는 id만 실재하는 계정이다."""

    def __init__(self, known: set[uuid.UUID] | None = None) -> None:
        self.known = known or set()
        self.added: list[object] = []

    def get(self, _model, user_id):
        return object() if user_id in self.known else None

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass


class TestCurrentUser:
    # 인자를 생략하면 FastAPI의 Header 기본값 객체가 들어온다(FastAPI가 실행
    # 시점에 풀어주는 값이다). 헤더가 없는 상태는 None을 명시해서 만든다.
    def test_no_headers_falls_back_to_dev(self):
        db = FakeDB({DEV_USER_ID})
        assert (
            get_current_user_id(authorization=None, x_user_id=None, db=db)
            == DEV_USER_ID
        )

    def test_dev_user_is_created_if_missing(self):
        # 볼륨을 지우고 마이그레이션 없이 뜬 경우. 첫 요청이 죽으면 안 된다.
        db = FakeDB()
        assert (
            get_current_user_id(authorization=None, x_user_id=None, db=db)
            == DEV_USER_ID
        )
        assert len(db.added) == 1

    def test_bearer_token_wins_over_x_user_id(self):
        me = uuid.uuid4()
        other = uuid.uuid4()
        token = create_access_token(str(me))
        assert (
            get_current_user_id(
                authorization=f"Bearer {token}",
                x_user_id=str(other),
                db=FakeDB({me, other}),
            )
            == me
        )

    def test_x_user_id_used_when_no_token(self):
        me = uuid.uuid4()
        assert (
            get_current_user_id(authorization=None, x_user_id=str(me), db=FakeDB({me}))
            == me
        )

    def test_broken_token_is_401_not_a_silent_fallback(self):
        # 조용히 dev로 떨어지면 만료된 토큰을 든 사람이 남의 자료를 본다.
        with pytest.raises(HTTPException) as exc:
            get_current_user_id(
                authorization="Bearer not-a-jwt", x_user_id=None, db=FakeDB()
            )
        assert exc.value.status_code == 401

    def test_token_subject_must_be_uuid(self):
        with pytest.raises(HTTPException) as exc:
            get_current_user_id(
                authorization=f"Bearer {create_access_token('hello')}",
                x_user_id=None,
                db=FakeDB(),
            )
        assert exc.value.status_code == 401

    def test_token_for_deleted_account_is_401(self):
        gone = uuid.uuid4()
        with pytest.raises(HTTPException) as exc:
            get_current_user_id(
                authorization=f"Bearer {create_access_token(str(gone))}",
                x_user_id=None,
                db=FakeDB(),
            )
        assert exc.value.status_code == 401

    def test_bad_x_user_id_is_400(self):
        with pytest.raises(HTTPException) as exc:
            get_current_user_id(authorization=None, x_user_id="nope", db=FakeDB())
        assert exc.value.status_code == 400

    def test_x_user_id_of_a_ghost_account_is_400(self):
        # 통과시키면 읽기는 되고 소유를 남기는 순간 FK가 터진다 — 업로드가
        # 500으로 죽고 원인은 로그에만 남는다.
        with pytest.raises(HTTPException) as exc:
            get_current_user_id(
                authorization=None, x_user_id=str(uuid.uuid4()), db=FakeDB()
            )
        assert exc.value.status_code == 400


class TestToken:
    def test_round_trip(self):
        sub = str(uuid.uuid4())
        assert decode_access_token(create_access_token(sub)) == sub

    def test_tampered_token_returns_none(self):
        token = create_access_token("someone")
        assert decode_access_token(token[:-2] + "xy") is None


class TestProviderNormalization:
    def test_google_is_flat(self):
        user = oauth._normalize(
            "google", {"sub": "1234", "email": "a@b.com", "name": "홍길동"}
        )
        assert (user.sub, user.email, user.name) == ("1234", "a@b.com", "홍길동")

    def test_naver_wraps_in_response(self):
        user = oauth._normalize(
            "naver",
            {"resultcode": "00", "response": {"id": "9", "email": "a@b.com"}},
        )
        assert (user.sub, user.email) == ("9", "a@b.com")

    def test_missing_email_is_502_not_a_broken_account(self):
        # 이메일 동의를 안 받으면 email이 빠져 온다. 그대로 만들면 이메일 없는
        # 계정이 생기고, 같은 사람이 다른 제공자로 들어올 때 합칠 근거가 없어진다.
        with pytest.raises(HTTPException) as exc:
            oauth._normalize("google", {"sub": "1234"})
        assert exc.value.status_code == 502


class TestConfigured:
    def test_blank_credentials_mean_not_configured(self, monkeypatch):
        monkeypatch.setattr(oauth.settings, "NAVER_CLIENT_ID", "  ")
        monkeypatch.setattr(oauth.settings, "NAVER_CLIENT_SECRET", "x")
        assert oauth.is_configured("naver") is False

    def test_both_filled(self, monkeypatch):
        monkeypatch.setattr(oauth.settings, "NAVER_CLIENT_ID", "id")
        monkeypatch.setattr(oauth.settings, "NAVER_CLIENT_SECRET", "secret")
        assert oauth.is_configured("naver") is True

    def test_redirect_uri_matches_the_callback_route(self, monkeypatch):
        # 이 문자열이 제공자 콘솔 등록값과 다르면 콜백에서 막힌다.
        monkeypatch.setattr(
            oauth.settings, "OAUTH_BACKEND_BASE_URL", "http://localhost:8000"
        )
        assert (
            oauth.redirect_uri("google")
            == "http://localhost:8000/api/auth/callback/google"
        )
