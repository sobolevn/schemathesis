import pytest

from schemathesis.constants import DEFAULT_DEADLINE, RECURSIVE_REFERENCE_ERROR_MESSAGE, USER_AGENT


def test_pytest_parametrize_fixture(testdir):
    # When `pytest_generate_tests` is used on a module level for fixture parametrization
    testdir.make_test(
        """
def pytest_generate_tests(metafunc):
    metafunc.parametrize("inner", ("A", "B"))

@pytest.fixture()
def param(inner):
    return inner * 2

@schema.parametrize()
def test_(request, param, case):
    request.config.HYPOTHESIS_CASES += 1
    assert case.full_path == "/v1/users"
    assert case.method in ("GET", "POST")
""",
        paths={
            "/users": {
                "get": {"responses": {"200": {"description": "OK"}}},
                "post": {"responses": {"200": {"description": "OK"}}},
            }
        },
    )
    # And there are multiple method/path combinations
    result = testdir.runpytest("-v", "-s")
    # Then the total number of tests should be method/path combos x parameters in `pytest_generate_tests`
    # I.e. regular pytest parametrization logic should be applied
    result.assert_outcomes(passed=4)
    result.stdout.re_match_lines(
        [
            r"test_pytest_parametrize_fixture.py::test_\[GET /v1/users\]\[P\]\[A\] PASSED",
            r"test_pytest_parametrize_fixture.py::test_\[GET /v1/users\]\[P\]\[B\] PASSED",
            r"test_pytest_parametrize_fixture.py::test_\[POST /v1/users\]\[P\]\[A\] PASSED",
            r"test_pytest_parametrize_fixture.py::test_\[POST /v1/users\]\[P\]\[B\] PASSED",
            r"Hypothesis calls: 4",
        ]
    )


def test_pytest_parametrize_class_fixture(testdir):
    # When `pytest_generate_tests` is used on a class level for fixture parametrization
    testdir.make_test(
        """
class TestAPI:

    def pytest_generate_tests(self, metafunc):
        metafunc.parametrize("inner", ("A", "B"))

    @pytest.fixture()
    def param(self, inner):
        return inner * 2

    @schema.parametrize()
    def test_(self, request, param, case):
        request.config.HYPOTHESIS_CASES += 1
        assert case.full_path == "/v1/users"
        assert case.method in ("GET", "POST")
""",
        paths={
            "/users": {
                "get": {"responses": {"200": {"description": "OK"}}},
                "post": {"responses": {"200": {"description": "OK"}}},
            }
        },
    )
    # And there are multiple method/path combinations
    result = testdir.runpytest("-v", "-s")
    # Then the total number of tests should be method/path combos x parameters in `pytest_generate_tests`
    # I.e. regular pytest parametrization logic should be applied
    result.assert_outcomes(passed=4)
    result.stdout.re_match_lines(
        [
            r"test_pytest_parametrize_class_fixture.py::TestAPI::test_\[GET /v1/users\]\[P\]\[A\] PASSED",
            r"test_pytest_parametrize_class_fixture.py::TestAPI::test_\[GET /v1/users\]\[P\]\[B\] PASSED",
            r"test_pytest_parametrize_class_fixture.py::TestAPI::test_\[POST /v1/users\]\[P\]\[A\] PASSED",
            r"test_pytest_parametrize_class_fixture.py::TestAPI::test_\[POST /v1/users\]\[P\]\[B\] PASSED",
            r"Hypothesis calls: 4",
        ]
    )


def test_pytest_collection_regression(testdir):
    # See #429.
    # When in a module scope there is an object that has custom `__getattr__` (a mock for example)
    testdir.make_test(
        """
from unittest.mock import call

def test_schemathesis():
    assert True
""",
    )
    result = testdir.runpytest()
    # It shouldn't be collected as a test
    result.assert_outcomes(passed=1)


def test_pytest_warning(testdir):
    testdir.make_test(
        """
@schema.parametrize()
def test_a(case):
    assert True

@schema.parametrize()
@pytest.mark.parametrize("a", (1, 2))
def test_b(case, a):
    assert True
""",
    )
    # When a test is run with treating warnings as errors
    result = testdir.runpytest("-Werror")
    # There should be no errors. There are no warnings from Schemathesis pytest plugin.
    result.assert_outcomes(passed=3)


def test_default_hypothesis_deadline(testdir):
    testdir.make_test(
        f"""
@schema.parametrize()
def test_a(case):
    assert settings().deadline.total_seconds() == {DEFAULT_DEADLINE} / 1000

@schema.parametrize()
@settings(max_examples=5)
def test_b(case):
    assert settings().deadline.total_seconds() == {DEFAULT_DEADLINE} / 1000

@schema.parametrize()
@settings(max_examples=5, deadline=100)
def test_c(case):
    assert settings().deadline.microseconds == 100 * 1000

def test_d():
    assert settings().deadline.microseconds == 200 * 1000
""",
    )
    # When there is a test with Pytest
    result = testdir.runpytest()
    # Then it should use the global Schemathesis deadline for Hypothesis (DEFAULT_DEADLINE value)
    result.assert_outcomes(passed=4)


def test_schema_given(testdir):
    # When the test uses `schema.given`
    testdir.make_test(
        """
from hypothesis.strategies._internal.core import DataObject

OPERATIONS = []

@schema.parametrize()
@schema.given(data=st.data())
def test_a(data, case):
    assert isinstance(data, DataObject)
    OPERATIONS.append(f"{case.method} {case.path}")


def teardown_module(module):
    assert OPERATIONS == ['GET /users', 'POST /users']
    """,
        paths={
            "/users": {
                "get": {"responses": {"200": {"description": "OK"}}},
                "post": {"responses": {"200": {"description": "OK"}}},
            }
        },
    )
    # Then its arguments should be proxied to the `hypothesis.given`
    # And be available in the test
    result = testdir.runpytest()
    result.assert_outcomes(passed=2)


def test_given_no_arguments(testdir):
    # When `schema.given` is used without arguments
    testdir.make_test(
        """
@schema.parametrize()
@schema.given()
def test(case):
    pass
        """,
    )
    # Then the wrapped test should fail with an error
    result = testdir.runpytest()
    result.assert_outcomes(failed=1)
    result.stdout.re_match_lines([".+given must be called with at least one argument"])


def test_given_no_override(testdir):
    # When `schema.given` is used multiple times on the same test
    testdir.make_test(
        """
@schema.parametrize()
@schema.given(st.booleans())
@schema.given(st.booleans())
def test(case):
    pass
        """,
    )
    # Then the wrapped test should fail with an error
    result = testdir.runpytest()
    result.assert_outcomes(failed=1)
    result.stdout.re_match_lines([".+You have applied `given` to the `test` test more than"])


def test_parametrize_no_override(testdir):
    # When `schema.parametrize` is used multiple times on the same test
    testdir.make_test(
        """
@schema.parametrize()
@schema.parametrize()
def test(case):
    pass
        """,
    )
    # Then the wrapped test should fail with an error
    result = testdir.runpytest()
    result.assert_outcomes(failed=1)
    result.stdout.re_match_lines([".+You have applied `parametrize` to the `test` test more than"])


def test_invalid_test(testdir):
    # When the test doesn't use the strategy provided in `schema.given`
    testdir.make_test(
        """
@schema.parametrize()
@schema.given(data=st.data())
def test(case):
    pass
    """,
    )
    # Then the test should fail instead of error
    result = testdir.runpytest()
    result.assert_outcomes(failed=1)


@pytest.mark.parametrize("style", ("python", "curl"))
def test_failure_reproduction_message(testdir, openapi3_base_url, style):
    # When a test fails
    testdir.make_test(
        f"""
schema.base_url = "{openapi3_base_url}"

@schema.parametrize(endpoint="failure")
def test(case):
    response = case.call()
    case.validate_response(response, code_sample_style="{style}")
    """,
        paths={"/failure": {"get": {"responses": {"200": {"description": "OK"}}}}},
    )
    # Then there should be a helpful message in the output
    result = testdir.runpytest()
    result.assert_outcomes(failed=1)
    if style == "python":
        lines = [
            r".+Run this Python code to reproduce this response:",
            rf".+requests.get\('{openapi3_base_url}/failure', headers={{'User-Agent': '{USER_AGENT}'",
        ]
    else:
        lines = [
            r".+Run this cURL command to reproduce this response:",
            rf".+curl -X GET -H 'Accept: \*/\*' -H 'Accept-Encoding: gzip, deflate' "
            rf"-H 'Connection: keep-alive' -H 'User-Agent: {USER_AGENT}' {openapi3_base_url}/failure",
        ]
    result.stdout.re_match_lines(
        [
            r".+1. Received a response with 5xx status code: 500",
            r".+2. Received a response with a status code, which is not defined in the schema: 500",
            r".+Declared status codes: 200",
        ]
        + lines
    )


def test_skip_operations_with_recursive_references(testdir, schema_with_recursive_references):
    # When the test schema contains recursive references
    testdir.make_test(
        """
@schema.parametrize()
def test(case):
    pass""",
        schema=schema_with_recursive_references,
    )
    result = testdir.runpytest("-rs")
    # Then this test should be skipped with a proper error message
    result.assert_outcomes(skipped=1)
    assert RECURSIVE_REFERENCE_ERROR_MESSAGE in result.stdout.str()


def test_checks_as_a_list(testdir, openapi3_base_url):
    # When the user passes a list of checks instead of a tuple
    testdir.make_test(
        f"""
schema.base_url = "{openapi3_base_url}"

def my_check(response, case):
    note("CHECKING!")

@schema.parametrize()
def test(case):
    response = case.call()
    case.validate_response(response, checks=(my_check,), additional_checks=[my_check])
""",
    )
    result = testdir.runpytest("-s")
    # Then it should work
    result.assert_outcomes(passed=1)
    assert "CHECKING!" in result.stdout.str()


@pytest.mark.parametrize(
    "body, expected",
    (
        ("raise AssertionError", "1. Check 'my_check' failed"),
        ("raise AssertionError('My message')", "1. My message"),
    ),
)
def test_failing_custom_check(testdir, openapi3_base_url, body, expected):
    # When the user passes a custom check that fails
    testdir.make_test(
        f"""
schema.base_url = "{openapi3_base_url}"

def my_check(response, case):
    {body}

def another_check(response, case):
    raise AssertionError("Another check")

@schema.parametrize()
def test(case):
    response = case.call()
    case.validate_response(response, checks=(my_check, another_check))
""",
    )
    result = testdir.runpytest("-s")
    result.assert_outcomes(failed=1)
    # Then the failure message should be displayed
    stdout = result.stdout.str()
    assert expected in stdout
    # And other failing checks are not ignored
    assert "Another check" in stdout


def test_no_collect_warnings(testdir):
    testdir.make_test(
        f"""
from schemathesis.models import *
    """,
    )
    result = testdir.runpytest()
    assert "cannot collect test class" not in result.stdout.str()
