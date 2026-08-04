import pytest
from pydantic import ValidationError

from checks import check_exc, equal
from settings import LogSettings, MultihostURL, PostgresSettings, ServerSettings, UrlBase

# Constants
driver = "driver"
username = "username%"
password = "password&"  # noqa: S105
host = "host"
host_v6 = "::1"
hosts = ("host1", "host2:22", "192.168.1.1", "192.168.1.2:23")
m_host_template = ",".join(host if ":" in host else (host + "{}") for host in hosts)
m_host = m_host_template.format("", "")
m_host_v6_template = "{}::1{},[::2]:6,{}3:4:5:6:7:8{},[9:10:11:12:13:14]{}"
m_host_v6 = m_host_v6_template.format("", "", "", "", "")
port = 123
port2 = 1234
db = "db"
query = {"key 1": "value +", "key": ("value 1", "value 2")}


msg_pass_wo_user = "User must be provided when providing password"  # noqa: S105
msg_hosts_w_host = "Cannot use hosts when host provided"
msg_hosts_wo_m_host = "Cannot use hosts when multihost is not supported"
msg_wrong_m_host_place = "Wrong multihost place provided: 'somewhere'"

# Results
r_driver = f"{driver}://"
r_username = username[:-1] + "%25"
r_password = password[:-1] + "%26"
r_port = f":{port}"
r_port_query = f"%3A{port}"
r_port2 = f":{port2}"
r_port2_query = f"%3A{port2}"
r_m_host_v6 = m_host_v6_template.format("[", "]", "[", "]", "")
r_m_host_port = m_host_template.format(r_port, r_port)
r_m_host_port2 = m_host_template.format(r_port2, r_port2)
r_m_host_v6_port = m_host_v6_template.format("[", f"]{r_port}", "[", f"]{r_port}", r_port)
r_db = f"/{db}"
r_query = "?key=value+1&key=value+2&key+1=value+%2B"
r_query_hosts_template = "?host=host1{}&host=host2%3A22&host=192.168.1.1{}&host=192.168.1.2%3A23"
r_query_hosts = r_query_hosts_template.format("", "")
r_query_hosts_port = r_query_hosts_template.format(r_port_query, r_port_query)
r_query_hosts_port2 = r_query_hosts_template.format(r_port2_query, r_port2_query)
r_scheme = "https://"


# Keyword arguments
kw_username = {"username": username}
kw_pass = {"password": password}
kw_host = {"host": host}
kw_host_v6 = {"host": host_v6}
kw_port = {"port": port}
kw_m_host = {"host": m_host}
kw_m_host_v6 = {"host": m_host_v6}
kw_db = {"database": db}
kw_query = {"query": query}

kw_hosts = {"hosts": hosts}

kw_user = {"user": username}
kw_single = {"hosts": (host,)}
kw_single_w_port = {"hosts": (f"{host}:{port2}",)}

kw_pg = kw_user | kw_pass | {"root_password": password}


class WrongMultihost(UrlBase):
    _multihost_place = "somewhere"


class AuthorityMultihost(UrlBase):
    _multihost_place = "authority"


class AuthorityMultihostWithPort(AuthorityMultihost):
    _multihost_default_port = port2


class QueryMultihost(UrlBase):
    _multihost_place = "query"


class QueryMultihostWithPort(QueryMultihost):
    _multihost_default_port = port2


all_m_host_cls = (
    AuthorityMultihost,
    QueryMultihost,
    AuthorityMultihostWithPort,
    QueryMultihostWithPort,
)
all_cls = (UrlBase, *all_m_host_cls)


# Params
fixed_url_params = [
    pytest.param(r_driver, {}, id="Driver"),
    pytest.param(r_driver + r_username + "@", kw_username, id="User"),
    pytest.param(r_driver, kw_pass, id="Password"),
    pytest.param(r_driver + r_username + ":***@", kw_username | kw_pass, id="User password"),
    pytest.param(r_driver + host, kw_host, id="Host"),
    pytest.param(r_driver + f"[{host_v6}]", kw_host_v6, id="Host IPv6"),
    pytest.param(r_driver + f"{host}:{port}", kw_host | kw_port, id="Host port"),
    pytest.param(r_driver + f"[{host_v6}]:{port}", kw_host_v6 | kw_port, id="Host IPv6 port"),
    pytest.param(r_driver + m_host, kw_m_host, id="Multihost"),
    pytest.param(r_driver + r_m_host_v6, kw_m_host_v6, id="Multihost IPv6"),
    pytest.param(r_driver + r_m_host_port, kw_m_host | kw_port, id="Multihost port"),
    pytest.param(r_driver + r_m_host_v6_port, kw_m_host_v6 | kw_port, id="Multihost IPv6 port"),
    pytest.param(r_driver + r_db, kw_db, id="Database"),
    pytest.param(r_driver + r_query, kw_query, id="Query"),
]

url_base_error_params = [
    pytest.param(UrlBase, msg_pass_wo_user, kw_pass, id="Password without user"),
    pytest.param(UrlBase, msg_hosts_w_host, kw_hosts | kw_host, id="Hosts with host"),
    pytest.param(UrlBase, msg_hosts_wo_m_host, kw_hosts, id="Hosts without multihost"),
    pytest.param(WrongMultihost, msg_wrong_m_host_place, kw_hosts, id="Wrong multihost place"),
]

url_base_params = [
    pytest.param(all_cls, r_username + ":***@localhost", kw_user | kw_pass, id="User, password"),
    pytest.param(all_cls, host, kw_host, id="Host"),
    pytest.param(all_cls, host + r_port, kw_host | kw_port, id="Host, port"),
    pytest.param(all_m_host_cls, host, kw_single, id="One hosts"),
    pytest.param(all_m_host_cls, host + r_port, kw_single | kw_port, id="One hosts, port"),
    pytest.param(all_m_host_cls, host + r_port2, kw_single_w_port, id="One hosts:port"),
    pytest.param(
        all_m_host_cls, host + r_port2, kw_single_w_port | kw_port, id="One hosts:port, port"
    ),
    pytest.param((QueryMultihost,), r_query_hosts, kw_hosts, id="Query"),
    pytest.param((QueryMultihost,), r_query_hosts_port, kw_hosts | kw_port, id="Query, port"),
    pytest.param((QueryMultihostWithPort,), r_query_hosts_port2, kw_hosts, id="Query:port"),
    pytest.param(
        (QueryMultihostWithPort,), r_query_hosts_port, kw_hosts | kw_port, id="Query:port, port"
    ),
    pytest.param((AuthorityMultihost,), m_host, kw_hosts, id="Authority"),
    pytest.param((AuthorityMultihost,), r_m_host_port, kw_hosts | kw_port, id="Authority, port"),
    pytest.param((AuthorityMultihostWithPort,), r_m_host_port2, kw_hosts, id="Authority:port"),
    pytest.param(
        (AuthorityMultihostWithPort,),
        r_m_host_port,
        kw_hosts | kw_port,
        id="Authority:port, port",
    ),
]


class TestFixedURL:
    name = "URL"

    @pytest.mark.parametrize(("expected", "kwargs"), fixed_url_params)
    def test_str(self, expected: str, kwargs: dict):
        equal(expected, str(MultihostURL.create(driver, **kwargs)), name=self.name)

    def test_show(self):
        expected = f"{r_driver}{r_username}:{r_password}@"
        received = MultihostURL.create(driver, **kw_username | kw_pass).render_as_string(False)  # noqa: FBT003
        equal(expected, received, name=self.name)

    def test_multihost_wrong_ipv6(self):
        with check_exc(ValueError, "Wrong multihost item='[::2]2'"):
            str(MultihostURL.create(driver, host="test1,[::2]2"))


class TestURLBase:
    name = "URLBase"

    @pytest.mark.parametrize(("cls", "msg", "kwargs"), url_base_error_params)
    def test_validation_errors(self, cls: type[UrlBase], msg: str, kwargs: dict):
        with check_exc(ValidationError, msg):
            cls(**kwargs)

    @pytest.mark.parametrize(("classes", "result", "kwargs"), url_base_params)
    def test_usage(self, classes: tuple[type[UrlBase], ...], result: str, kwargs: dict):
        for cls in classes:
            equal(r_scheme + result, str(cls(**kwargs).app_url), name=self.name)


class TestPostgresSettings:
    name = "PostgresSettings"

    def test_root_url(self):
        expected = f"postgresql+asyncpg://postgres:{r_password}@localhost/postgres"
        received = PostgresSettings(**kw_pg).root_url.render_as_string(hide_password=False)
        equal(expected, received, name=self.name)

    def test_test_url(self):
        expected = f"postgresql://{r_username}:{r_password}@localhost/auth"
        received = PostgresSettings(**kw_pg).test_url.render_as_string(hide_password=False)
        equal(expected, received, name=self.name)


class TestMergeWithDefault:
    name = "MergeWithDefault"

    def test_usage(self):
        fields, data = LogSettings.__pydantic_fields__, {"key": "value"}
        default = fields["common_kw"].default | fields["console_kw"].default
        equal(default, LogSettings().console_kw, name=self.name)
        equal(default | data, LogSettings(console_kw=data).console_kw)


class TestExtraSettings:
    name = "ExtraSettings"

    def test_extra_kw(self):
        equal({}, ServerSettings().extra_kw, name=self.name)
        with check_exc(ValueError, "Field ServerSettings.extra_kw has exists fields: port"):
            ServerSettings(extra_kw={"port": 12345})
        with check_exc(TypeError, "Config.__init__() got an unexpected keyword argument 'wrong'"):
            ServerSettings(extra_kw={"wrong": "not_exists_field"})

    def test_as_dict(self):
        default, extra = ServerSettings().as_dict(), {"loop": "none"}
        equal(default | extra, ServerSettings(extra_kw=extra).as_dict(), name=self.name)
