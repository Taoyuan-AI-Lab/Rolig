export type MemeMediaType = 'video' | 'image';

export interface Meme {
  id: string;
  url: string;
  type: MemeMediaType;
  tags: string[];
  score: number;
}
