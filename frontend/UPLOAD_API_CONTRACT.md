# Secure upload API contract

The Rolig client uploads media with a short-lived, single-object URL. It never
receives an R2 account token, Supabase service-role key, OpenAI key, or other
privileged credential.

All three endpoints below must require an authenticated Rolig session. Browser
clients send the HTTP-only session cookie with `credentials: include`. When
native authentication is added, the same API should accept its short-lived
bearer session token. The backend must derive the uploader identity from that
session rather than trusting a client-provided creator ID.

## 1. Create an upload session

`POST /api/v1/uploads/presign`

```json
{
  "contentType": "video/mp4",
  "fileName": "reaction.mp4",
  "mediaType": "video",
  "sizeBytes": 12345678
}
```

`201 Created`

```json
{
  "uploadId": "upl_01K...",
  "uploadUrl": "https://<signed-r2-url>",
  "headers": {
    "Content-Type": "video/mp4"
  },
  "expiresAt": "2026-07-25T18:10:00Z"
}
```

The backend generates both `uploadId` and the R2 object key. The signed URL
should expire within five minutes, permit only `PUT`, and be constrained to the
declared object, content type, and content length when supported.

## 2. Upload bytes to R2

The client sends the selected file directly to `uploadUrl` with `PUT` and the
exact response `headers`. A successful R2 response can be any 2xx status.

This URL is sensitive while valid. Do not log its query string or return it
from status endpoints.

## 3. Complete and moderate

`POST /api/v1/uploads/{uploadId}/complete`

```json
{
  "attribution": {
    "creatorName": "@original_creator",
    "sourceUrl": "https://source.example/original-post",
    "license": "Permission granted",
    "permissionConfirmed": true
  }
}
```

`200 OK`

```json
{
  "uploadId": "upl_01K...",
  "memeId": "e6a2b7a8-...",
  "status": "processing",
  "message": null
}
```

The backend should `HEAD` the object and verify its actual byte size and media
signature before creating the meme record. Images should have metadata stripped;
videos should be probed/transcoded into an approved streaming format. New media
remains in a private quarantine prefix or bucket until GPT safety analysis
returns `ready`.

For video analysis, the backend—not the mobile client—should extract and store
the representative frame required by the existing meme analysis service.

## 4. Read processing status

`GET /api/v1/uploads/{uploadId}`

```json
{
  "uploadId": "upl_01K...",
  "memeId": "e6a2b7a8-...",
  "status": "ready",
  "message": "Published"
}
```

`status` is one of `processing`, `ready`, or `rejected`. Only the uploader (or
an administrator) may read it. The client polls for up to 30 seconds and then
allows the user to close the modal while processing continues.

## Required backend controls

- Authenticate, authorize, rate-limit, and apply per-account storage quotas.
- Permit only the image/video MIME types and maximum sizes agreed with the
  client; verify file signatures because client validation is not authoritative.
- Generate opaque object keys and never use an untrusted filename as an R2 key.
- Keep pending and rejected uploads private and delete abandoned sessions with
  an R2 lifecycle rule.
- Store attribution and permission evidence with the meme record.
- Publish only after file validation and safety moderation both succeed.
- Restrict R2 CORS to the deployed Rolig origins and required methods/headers.
- Return generic errors without credential, bucket, object-key, or signed-URL
  details.

Expected error statuses are `401/403` for authorization, `413` for size,
`415/422` for invalid media or attribution, and `429` for rate limiting.
