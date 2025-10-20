// Common API response types
export interface ApiResponse<T> {
  data?: T;
  error?: ApiError;
  success: boolean;
}

export interface ApiError {
  message: string;
  code?: string;
  details?: Record<string, unknown>;
}

// Pagination types
export interface PageInfo {
  hasNextPage: boolean;
  hasPreviousPage: boolean;
  startCursor?: string;
  endCursor?: string;
}

export interface Connection<T> {
  edges: Array<Edge<T>>;
  pageInfo: PageInfo;
  totalCount: number;
}

export interface Edge<T> {
  node: T;
  cursor: string;
}

// Common filter types
export interface DateRange {
  from?: Date | string;
  to?: Date | string;
}

export interface SearchFilter {
  search?: string;
}

// File upload types
export interface FileUploadMetadata {
  fileName: string;
  fileType: string;
  fileSize: number;
  uploadedAt: Date;
}

export interface PresignedUrlResponse {
  url: string;
  fileName: string;
  key: string;
  expiresAt: string;
}