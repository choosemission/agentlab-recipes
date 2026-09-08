"""Exercise the participant client against the real example agent and wire errors."""
import asyncio
import json
from pathlib import Path

import httpx
import pytest
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette

import a2a_client as client
from agent.agent import create_agent_card, IdentityMirrorExecutor


def test_client_and_example_agent_use_v1(capsys):
    async def run():
        card = create_agent_card('http://example.test')
        handler = DefaultRequestHandler(agent_card=card, agent_executor=IdentityMirrorExecutor(), task_store=InMemoryTaskStore())
        app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, rpc_url='/')])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as http:
            resolved = await client.resolve_card(http, 'http://example.test')
            client.describe_card(resolved, 'http://example.test')
            endpoint = client.check_route(resolved, 'http://example.test')
            first = await client.send(http, endpoint, 'hello', 'Test name', '1.0.0', None, None, False)
            second = await client.send(http, endpoint, 'again', 'Test name', '1.0.0', first['context_id'], None, False)
            assert first['state'] == second['state'] == 'TASK_STATE_COMPLETED'
            assert first['context_id'] == second['context_id']
            assert first['task_id'] != second['task_id']
    asyncio.run(run())
    output = capsys.readouterr().out
    assert 'A2A version 1.0' in output and 'App version' in output
    assert "name='Test name'" in output


def test_wire_headers_and_jsonrpc_error_are_preserved(capsys):
    def respond(request):
        body = json.loads(request.content)
        assert request.headers['A2A-Version'] == '1.0'
        assert request.headers['A2A-Extensions'] == client.IDENTITY_EXT_URI
        assert body['method'] == 'SendMessage'
        assert body['params']['message']['role'] == 'ROLE_USER'
        assert body['params']['message']['parts'] == [{'text': 'hello'}]
        assert 'x-api-key' not in request.headers
        return httpx.Response(200, json={'jsonrpc': '2.0', 'id': body['id'], 'error': {'code': -32601, 'message': 'Method not found'}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            with pytest.raises(ValueError, match='Method not found'):
                await client.send(http, 'http://example.test/', 'hello', 'test', '1.0.0', None, None, True)
    asyncio.run(run())
    assert '"error"' in capsys.readouterr().out


def test_old_card_is_reported_as_incompatible():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'protocolVersion': '0.3.0', 'version': '1.0.0'}))) as http:
            with pytest.raises(ValueError, match='advertises A2A 0.3.0'):
                await client.resolve_card(http, 'https://gateway.test/agent')
    asyncio.run(run())


@pytest.mark.parametrize('url', ['https://target.test/agent', 'https://gateway.test/other', 'http://gateway.test/agent', 'https://gateway.test/agent/../other', 'https://gateway.test/agent/%2e%2e/other'])
def test_discovery_cannot_silently_bypass_the_access_point(url):
    with pytest.raises(ValueError, match='outside the access point'):
        client.check_route(create_agent_card(url), 'https://gateway.test/agent')


def test_gateway_interface_with_subpath_is_accepted():
    assert client.check_route(create_agent_card('https://gateway.test/agent/rpc'), 'https://gateway.test/agent') == 'https://gateway.test/agent/rpc/'


def test_replay_displays_binding_without_changing_identity_metadata(capsys):
    fixture = Path(__file__).parents[1] / 'fixtures/example-response.json'
    state = client.report(json.loads(fixture.read_text()), False)
    assert state['state'] == 'TASK_STATE_COMPLETED'
    output = capsys.readouterr().out
    assert 'workload binding' in output and 'userIdentity.id' in output
    assert 'ROLE_HELLO' not in output
