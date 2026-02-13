# Testing Conventions

## Test Stack
- **pytest 8.0+** — Test framework
- **pytest-asyncio 0.23+** — Async test support (`asyncio_mode = "auto"`)
- **pytest-cov 4.1+** — Coverage reporting
- **unittest.mock** — Mocking (patch, MagicMock, AsyncMock)

## Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

All async test functions are automatically detected — no need for `@pytest.mark.asyncio`.

## Directory Structure

```
tests/
├── test_classify.py       # Classification prompts, engine wiring, LLM mock
├── test_rules.py          # Rule-based classification patterns
├── test_lifecycle.py      # Email state machine transitions
├── test_db.py             # Database operations, repository pattern
├── test_gmail_models.py   # Gmail API model parsing
└── conftest.py            # Shared fixtures (if present)
```

## Test Patterns

### Async Tests

```python
async def test_classify_email(tmp_path):
    """Tests are automatically async — no decorator needed."""
    db = await create_test_db(tmp_path)
    engine = ClassificationEngine(mock_llm_gateway)
    result = await engine.classify(email_data)
    assert result.classification == "needs_response"
    assert result.confidence == "high"
```

### Database Tests (In-Memory SQLite)

```python
async def test_email_repository(tmp_path):
    db = Database(tmp_path / "test.db")
    await db.initialize()
    repo = EmailRepository(db)

    await repo.create(user_id=1, gmail_thread_id="thread123", ...)
    email = await repo.get_by_thread_id(1, "thread123")
    assert email["classification"] == "pending"
```

### Mocking Gmail API

```python
from unittest.mock import MagicMock, patch

def mock_gmail_service():
    service = MagicMock()
    service.users().messages().get().execute.return_value = {
        "id": "msg123",
        "threadId": "thread123",
        "payload": {"headers": [{"name": "From", "value": "test@example.com"}]},
    }
    return service
```

### Mocking LLM Gateway

```python
from unittest.mock import AsyncMock

mock_llm = AsyncMock(spec=LLMGateway)
mock_llm.classify.return_value = {
    "classification": "needs_response",
    "confidence": "high",
    "reasoning": "Direct question requiring reply",
    "language": "en",
    "style": "casual",
}
mock_llm.draft.return_value = "Thank you for your message..."
```

### Classification Rule Tests

```python
def test_rule_matches_newsletter():
    rules = RuleEngine()
    result = rules.classify(sender="noreply@newsletter.com", subject="Weekly Digest")
    assert result.classification == "fyi"
    assert result.confidence == "high"

def test_rule_defers_to_llm():
    rules = RuleEngine()
    result = rules.classify(sender="colleague@work.com", subject="Quick question")
    assert result.confidence == "low"  # Low confidence → LLM fallback
```

### Lifecycle State Machine Tests

```python
async def test_done_transition():
    manager = LifecycleManager(db, gmail_service)
    await manager.handle_done(user_id=1, thread_id="thread123")
    email = await email_repo.get_by_thread_id(1, "thread123")
    assert email["status"] == "archived"

async def test_rework_increments_count():
    manager = LifecycleManager(db, gmail_service)
    await manager.handle_rework(user_id=1, thread_id="thread123", instruction="Make it shorter")
    email = await email_repo.get_by_thread_id(1, "thread123")
    assert email["rework_count"] == 1
```

## Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_classify.py

# Specific test
pytest tests/test_classify.py::test_classify_email

# With coverage
pytest --cov=src --cov-report=term-missing

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

## Best Practices

1. **Use `tmp_path` for database tests** — Each test gets an isolated SQLite database
2. **Mock external services** — Never hit Gmail API or LLM in tests
3. **Use `AsyncMock` for async interfaces** — LLM gateway, Gmail client
4. **Test classification rules separately from LLM** — Rules are deterministic, fast to test
5. **Test lifecycle transitions independently** — State machine logic is pure, no LLM needed
6. **Keep tests focused** — One behavior per test function
7. **Name tests descriptively** — `test_rework_rejects_after_three_attempts` not `test_rework_3`
