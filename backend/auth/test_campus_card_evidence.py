# 2026-11-19 - David Noyes - Printable real callback log evidence, isolated data only.
import os
import time
import pytest
from backend.auth.test_campus_staff_app import BASE, setup, campus_token
from campus_sso.campus_provider import TOKEN_TTL, token_serializer


@pytest.mark.parametrize('case,result,status', [
    ('accepted', 'identity_accepted', 302),
    ('student', 'no_staff_role', 403),
    ('changed', 'invalid_signature', 403),
    ('expired', 'expired_token', 403),
])
def test_card_evidence(setup, caplog, case, result, status):
    client = setup[0]
    token = campus_token(setup, 'campus_student' if case == 'student' else 'campus_staff')
    if case == 'changed':
        token = ('A' if token[0] != 'A' else 'B') + token[1:]
    if case == 'expired':
        signer = token_serializer(os.environ['CAMPUS_SSO_SIGNING_KEY'])
        claims = signer.loads(token)
        claims['iat'] = int(time.time()) - TOKEN_TTL - 5
        claims['exp'] = claims['iat'] + TOKEN_TTL
        token = signer.dumps(claims)
    caplog.clear()
    with caplog.at_level('INFO', logger=client.application.logger.name):
        response = client.post(BASE + '/auth/campus/callback', data={'token': token})
    assert response.status_code == status
    assert client.get(BASE + '/staff').status_code == 403  # Even accepted identity still needs MFA.
    expected_id = {'accepted': 'CAMPUS-1001', 'student': 'CAMPUS-2001'}.get(case, '-')
    message = f'event=campus_sso | result={result} | campus_id={expected_id}'
    assert message in caplog.messages
    assert token not in caplog.text and setup[2] not in caplog.text
    print(f'ISOLATED INTEGRATION EVIDENCE: {case} -> HTTP {status}\n{message}')
