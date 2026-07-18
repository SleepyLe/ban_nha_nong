import httpx

from app.backend import notify


def _ticket(phone: str = "090 123-4567") -> dict:
    return {
        "id": 42,
        "contact_phone": phone,
        "contact_name": "Bà con kiểm thử",
        "question": "Câu hỏi thử",
        "answer": "Câu trả lời thử",
        "answered_by": "Cán bộ thử",
    }


def test_notify_answer_sends_speedsms(monkeypatch) -> None:
    calls = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"status": "success", "code": "00", "data": {"tranId": 1}}

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("ZALO_OA_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("SPEEDSMS_ACCESS_TOKEN", "sms-test-token")
    monkeypatch.setenv("SPEEDSMS_SMS_TYPE", "4")
    monkeypatch.setenv("SPEEDSMS_SENDER", "Notify")
    monkeypatch.setattr(httpx, "post", post)

    assert notify.notify_ticket_answered(_ticket()) == "sms"
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == "https://api.speedsms.vn/index.php/sms/send"
    assert kwargs["auth"] == ("sms-test-token", "x")
    assert kwargs["json"]["to"] == ["84901234567"]
    assert kwargs["json"]["sms_type"] == 4
    assert kwargs["json"]["sender"] == "Notify"
    assert len(kwargs["json"]["content"]) <= 160


def test_speedsms_failure_does_not_break_officer_answer(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"status": "error", "code": "300", "message": "no balance"}

    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("ZALO_OA_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("SPEEDSMS_ACCESS_TOKEN", "sms-test-token")
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: Response())

    assert notify.notify_ticket_answered(_ticket()) == "none"


def test_invalid_phone_skips_sms_without_raising(monkeypatch) -> None:
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("ZALO_OA_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("SPEEDSMS_ACCESS_TOKEN", "sms-test-token")

    assert notify.notify_ticket_answered(_ticket("abc")) == "none"


def test_email_and_sms_are_recorded_together(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SPEEDSMS_ACCESS_TOKEN", "sms-test-token")
    monkeypatch.delenv("ZALO_OA_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(notify, "_send_email", lambda ticket: None)
    monkeypatch.setattr(notify, "_send_sms", lambda ticket, token: None)
    ticket = _ticket()
    ticket["contact_email"] = "farmer@example.com"

    assert notify.notify_ticket_answered(ticket) == "email,sms"
