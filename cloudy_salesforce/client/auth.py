import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from xml.sax.saxutils import escape

import jwt
import requests
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)

JWT_BEARER_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"


class BaseAuthentication(ABC):
    def __init__(self, session: requests.Session, instance_url: str):
        self.session = session
        self.instance_url = instance_url

    @abstractmethod
    def authenticate(self) -> tuple[requests.Session, str]:
        pass

    @staticmethod
    def get_headers(access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }


class UsernamePasswordAuthentication(BaseAuthentication):
    def __init__(
        self,
        username: str,
        password: str,
        security_token: str,
        login_url: str = "https://login.salesforce.com",
        api_version: str = "v61.0",
    ):
        self.username = username
        self.password = password
        self.security_token = security_token
        self.login_url = login_url
        self.api_version = api_version
        session, instance_url = self.authenticate()
        super().__init__(session, instance_url)

    def authenticate(self) -> tuple[requests.Session, str]:
        session = requests.Session()
        soap_version = self.api_version.removeprefix("v")
        auth_url = f"{self.login_url}/services/Soap/u/{soap_version}"
        headers = {"Content-Type": "text/xml", "SOAPAction": "login"}
        escaped_username = escape(self.username)
        escaped_password = escape(f"{self.password}{self.security_token}")
        soap_body = f"""
        <env:Envelope xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
            <env:Body>
                <n1:login xmlns:n1="urn:partner.soap.sforce.com">
                    <n1:username>{escaped_username}</n1:username>
                    <n1:password>{escaped_password}</n1:password>
                </n1:login>
            </env:Body>
        </env:Envelope>
        """
        try:
            response = session.post(
                auth_url, headers=headers, data=soap_body, timeout=30
            )
            response.raise_for_status()
            response_content = response.content.decode("utf-8")
            if "faultstring" in response_content:
                raise Exception(f"SOAP Fault: {response_content}")
            access_token = self._extract_access_token(response_content)
            instance_url = self._extract_instance_url(response_content)
            logger.info("Authentication successful")
            session.headers.update(self.get_headers(access_token))
            return session, instance_url
        except HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err}")
            raise
        except Exception as err:
            logger.error(f"Other error occurred: {err}")
            raise

    def _extract_tag(self, response_content: str, tag: str) -> str:
        start_tag = f"<{tag}>"
        end_tag = f"</{tag}>"
        start_index = response_content.find(start_tag)
        end_index = response_content.find(end_tag)
        if start_index == -1 or end_index == -1:
            raise ValueError(f"SOAP response missing <{tag}>")
        return response_content[start_index + len(start_tag) : end_index]

    def _extract_access_token(self, response_content: str) -> str:
        return self._extract_tag(response_content, "sessionId")

    def _extract_instance_url(self, response_content: str) -> str:
        server_url = self._extract_tag(response_content, "serverUrl")
        return server_url.split("/services")[0]


class SessionAuthentication(BaseAuthentication):
    def __init__(self, access_token: str, instance_url: str):
        self.access_token = access_token
        session = requests.Session()
        session.headers.update(self.get_headers(access_token))
        super().__init__(session, instance_url)

    def authenticate(self) -> tuple[requests.Session, str]:
        return self.session, self.instance_url


class JwtBearerAuthentication(BaseAuthentication):
    def __init__(
        self,
        client_id: str,
        username: str,
        private_key: str | None = None,
        *,
        private_key_path: str | None = None,
        login_url: str = "https://login.salesforce.com",
    ):
        self.client_id = client_id
        self.username = username
        self.login_url = login_url
        if private_key is not None:
            self.private_key = private_key
        elif private_key_path is not None:
            self.private_key = Path(private_key_path).read_text(encoding="utf-8")
        else:
            raise ValueError("Either private_key or private_key_path is required")
        session, instance_url = self.authenticate()
        super().__init__(session, instance_url)

    def _build_assertion(self) -> str:
        payload = {
            "iss": self.client_id,
            "sub": self.username,
            "aud": self.login_url,
            "exp": int(time.time()) + 180,
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    def authenticate(self) -> tuple[requests.Session, str]:
        session = requests.Session()
        token_url = f"{self.login_url}/services/oauth2/token"
        assertion = self._build_assertion()
        try:
            response = session.post(
                token_url,
                data={
                    "grant_type": JWT_BEARER_GRANT_TYPE,
                    "assertion": assertion,
                },
                timeout=30,
            )
            response.raise_for_status()
            token_data = response.json()
            access_token = token_data["access_token"]
            instance_url = token_data["instance_url"]
            logger.info("JWT bearer authentication successful")
            session.headers.update(self.get_headers(access_token))
            return session, instance_url
        except HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err}")
            raise
        except Exception as err:
            logger.error(f"Other error occurred: {err}")
            raise
