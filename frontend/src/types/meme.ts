export type MemeMediaType = 'video' | 'image';

export interface Meme {
  creatorId: string;
  creatorUsername?: string;
  id: string;
  likeCount: number;
  musicTitle?: string;
  summary: string;
  url: string;
  type: MemeMediaType;
  tags: string[];
  score: number;
  viewCount: number;
}
