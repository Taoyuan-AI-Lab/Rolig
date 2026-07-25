import type { MemeMediaType } from './meme';

export const UPLOAD_LICENSES = [
  'Permission granted',
  'Original content',
  'Creative Commons',
  'Public domain',
] as const;

export type UploadLicense = (typeof UPLOAD_LICENSES)[number];

export interface UploadAttribution {
  creatorName: string;
  license: UploadLicense;
  permissionConfirmed: boolean;
  sourceUrl: string;
}

export interface UploadMedia {
  file?: File;
  fileName: string;
  fileSize: number;
  height: number;
  mediaType: MemeMediaType;
  mimeType: string;
  uri: string;
  width: number;
}

export type UploadProcessingStatus = 'processing' | 'ready' | 'rejected';

export interface UploadSession {
  expiresAt: string;
  headers: Record<string, string>;
  uploadId: string;
  uploadUrl: string;
}

export interface UploadResult {
  memeId: string | null;
  message: string | null;
  status: UploadProcessingStatus;
  uploadId: string;
}
