from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aioboto3
import aiofiles

from app.config import Settings


@dataclass(frozen=True, slots=True)
class StoredObject:
    content_length: int
    content_type: str
    etag: str | None


class R2Storage:
    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        quarantine_bucket_name: str,
        public_base_url: str,
    ) -> None:
        self._endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self.bucket_name = bucket_name
        self.quarantine_bucket_name = quarantine_bucket_name
        self.public_base_url = public_base_url.rstrip("/")
        self._session = aioboto3.Session()

    @classmethod
    def from_settings(cls, settings: Settings) -> "R2Storage":
        return cls(
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id.get_secret_value(),
            secret_access_key=settings.r2_secret_access_key.get_secret_value(),
            bucket_name=settings.r2_bucket_name,
            quarantine_bucket_name=settings.r2_quarantine_bucket_name,
            public_base_url=settings.r2_public_base_url,
        )

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[Any]:
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key_id,
            aws_secret_access_key=self._secret_access_key,
            region_name="auto",
        ) as client:
            yield client

    async def create_put_url(
        self,
        *,
        object_key: str,
        content_type: str,
        expires_in: int,
    ) -> str:
        async with self._client() as client:
            return await client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.quarantine_bucket_name,
                    "Key": object_key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
                HttpMethod="PUT",
            )

    async def create_get_url(self, *, object_key: str, expires_in: int = 300) -> str:
        async with self._client() as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.quarantine_bucket_name, "Key": object_key},
                ExpiresIn=expires_in,
                HttpMethod="GET",
            )

    async def head(self, object_key: str) -> StoredObject:
        async with self._client() as client:
            response = await client.head_object(
                Bucket=self.quarantine_bucket_name,
                Key=object_key,
            )
        return StoredObject(
            content_length=int(response["ContentLength"]),
            content_type=str(response.get("ContentType") or "application/octet-stream"),
            etag=str(response["ETag"]).strip('"') if response.get("ETag") else None,
        )

    async def read_prefix(self, object_key: str, length: int = 16) -> bytes:
        async with self._client() as client:
            response = await client.get_object(
                Bucket=self.quarantine_bucket_name,
                Key=object_key,
                Range=f"bytes=0-{length - 1}",
            )
            return await response["Body"].read(length)

    async def download_to(self, object_key: str, destination: Path) -> None:
        async with self._client() as client:
            response = await client.get_object(
                Bucket=self.quarantine_bucket_name,
                Key=object_key,
            )
            body = response["Body"]
            async with aiofiles.open(destination, "wb") as output:
                while chunk := await body.read(1024 * 1024):
                    await output.write(chunk)

    async def upload_file(
        self,
        source: Path,
        object_key: str,
        *,
        content_type: str,
        cache_control: str | None = None,
        public: bool = False,
    ) -> None:
        extra_args: dict[str, str] = {"ContentType": content_type}
        if cache_control:
            extra_args["CacheControl"] = cache_control
        async with self._client() as client:
            await client.upload_file(
                str(source),
                self.bucket_name if public else self.quarantine_bucket_name,
                object_key,
                ExtraArgs=extra_args,
            )

    async def delete(self, object_key: str, *, public: bool = False) -> None:
        async with self._client() as client:
            await client.delete_object(
                Bucket=self.bucket_name if public else self.quarantine_bucket_name,
                Key=object_key,
            )

    def public_url(self, object_key: str) -> str:
        return f"{self.public_base_url}/{object_key}"
