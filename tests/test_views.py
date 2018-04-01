import datetime
from contextlib import contextmanager

from flask import request, template_rendered, session
from konsent import app
import konsent

import pytest
from unittest.mock import MagicMock


# http://flask.pocoo.org/docs/0.12/signals/#subscribing-to-signals
@contextmanager
def captured_templates(app):
    recorded = []
    def record(sender, template, context, **extra):
        recorded.append((template, context))
    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)


@pytest.fixture()
def client():
    app.config['TESTING'] = True
    app.secret_key = 'test_views'
    with app.test_client() as client:
        yield client


@pytest.fixture
def user_mock(mocker):
    User_mock = mocker.patch('konsent.User')

    user_stab = MagicMock()
    user_stab.union.union_name = 'test_union'
    user_stab.union.id = '1'
    user_stab.id = '1'
    user_stab.check_password.return_value = True

    User_mock.query.filter().first.return_value = user_stab


@pytest.fixture
def orm_mock(mocker):
    db = mocker.patch('konsent.db')
    mocker.patch('konsent.update_phases')

    Post_mock = mocker.patch('konsent.Post')

    post_stub = MagicMock()
    post_stub.time_since_create = {'hours': 0}
    post_stub.union_id = '1'

    Post_mock.query.filter().all.return_value = [post_stub]

    Post_mock.query.filter().filter().all.return_value = [post_stub]
    Post_mock.create_date = datetime.datetime.now()

    Post_mock.query.get.return_value = post_stub

    UpvoteForm_mock = mocker.patch('konsent.UpvoteForm')
    UpvoteForm_mock().validate.return_value = True

    CommentForm_mock = mocker.patch('konsent.CommentForm')
    CommentForm_mock().validate.return_value = True

    Union_mock = mocker.patch('konsent.Union')
    Union_mock.query.filter().count.return_value = 1

    Vote_mock = mocker.patch('konsent.Vote')
    Vote_query = Vote_mock.query.filter().first

    Comment_mock = mocker.patch('konsent.Comment')
    comment_stub = MagicMock()
    Comment_mock.return_value = comment_stub

    return locals()


@pytest.fixture()
def client_logged(user_mock):
    app.config['TESTING'] = True
    app.secret_key = 'test_views'

    data = {'username': 'test_user',
            'password': 'test_password'}

    with app.test_client() as client:
        client.post('/login', data=data)
        yield client


def is_logged_in_stub(func):
    def wrap(*args, **kwargs):
        return func(*args, **kwargs)


def test_index(client):
    response = client.get('/')
    assert b'Konsent' in response.data


def test_login_non_existing_user(client, mocker):
    User_mock = mocker.patch('konsent.User')
    User_mock.query.filter().first.return_value = None

    data = {'username': 'test_user',
            'password': 'test_password'}

    with captured_templates(app) as templates:

        response = client.post('/login', data=data)

        assert not session

        assert response.status == '200 OK'
        [template, context], *_ = templates
        assert template.name == 'login.html'
        assert context['error']


def test_login_existing_user(client, user_mock):

    data = {'username': 'test_user',
            'password': 'test_password'}


    response = client.post('/login', data=data)

    assert  session['logged_in'] == True
    assert  session['username'] == 'test_user'
    assert  session['user_id'] == '1'
    assert  session['connected_union'] == '1'

    assert response.status == '302 FOUND'
    assert b"Redirecting" in response.data
    assert response.headers['Location'].endswith('/')


def test_phase1(client_logged, orm_mock):
    with captured_templates(app) as templates:

        response = client_logged.get('/phase1')

        assert response.status == '200 OK'
        [template, context], *_ = templates
        assert template.name == 'phase1.html'
        assert context['posts'] == [orm_mock['post_stub']]


def test_phase2(client_logged, orm_mock):
    with captured_templates(app) as templates:

        response = client_logged.get('/phase2')

        assert response.status == '200 OK'
        [template, context], *_ = templates
        assert template.name == 'phase2.html'
        assert context['posts'] == [orm_mock['post_stub']]


def test_phase3(client_logged, orm_mock):
    with captured_templates(app) as templates:

        response = client_logged.get('/phase3')

        assert response.status == '200 OK'
        [template, context], *_ = templates
        assert template.name == 'phase3.html'
        assert context['posts'] == [orm_mock['post_stub']]


def test_post1_get(client_logged, orm_mock):
    with captured_templates(app) as templates:

        response = client_logged.get('/phase1/post/1')

        assert response.status == '200 OK'
        [template, context], *_ = templates
        assert template.name == 'post.html'
        assert context['post_data']['voted'] == True
        # MagicMock __len__ returns 0
        assert context['post_data']['votes'] == 0


def test_post1_post_vote_up(client_logged, orm_mock):
    orm_mock['Vote_query'].return_value = None
    orm_mock['post_stub'].votes_count = 0

    with captured_templates(app) as templates:

        response = client_logged.post('/phase1/post/1',
                                      data={'minutes': 0, 'hours': 0}, follow_redirects=True)

        assert response.status == '200 OK'

        [template, context], *_ = templates
        assert template.name == 'phase1.html'

        assert orm_mock['post_stub'].votes_count == 1


def test_post1_post_vote_down(client_logged, orm_mock, mocker):
    orm_mock['post_stub'].votes_count = 1

    with captured_templates(app) as templates:

        response = client_logged.post('/phase1/post/1',
                                      data={'minutes': 0, 'hours': 0},
                                      follow_redirects=True)

        assert response.status == '200 OK'
        [template, context], *_ = templates
        assert template.name == 'phase1.html'
        assert orm_mock['post_stub'].votes_count == 0


def test_post2_get(client_logged, orm_mock):
    with captured_templates(app) as templates:

        response = client_logged.get('/phase2/post/1')

        assert response.status == '200 OK'
        [template, context], *_ = templates
        assert template.name == 'post.html'
        assert context['post'] == orm_mock['post_stub']


def test_post2_post(client_logged, orm_mock):
    with captured_templates(app) as templates:

        response = client_logged.post('/phase2/post/1')

        assert response.status == '200 OK'
        [template, context], *_ = templates
        assert template.name == 'post.html'
        assert context['post'] == orm_mock['post_stub']
        orm_mock['db'].session.add.assert_called_with(orm_mock['comment_stub'])