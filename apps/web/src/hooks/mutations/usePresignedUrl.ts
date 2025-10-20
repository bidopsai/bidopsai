/**
 * usePresignedUrl Hook
 *
 * Mutation hook for generating S3 presigned URLs
 */

import { useMutation } from '@tanstack/react-query';
import { graphqlMutation } from '@/lib/graphql/client';
import { GENERATE_PRESIGNED_URLS } from '@/lib/graphql/mutations/projects';
import { toast } from 'sonner';

interface PresignedUrlRequest {
  fileName: string;
  fileType: string;
  fileSize: number;
}

interface PresignedUrlInput {
  projectId: string;
  files: PresignedUrlRequest[];
}

interface PresignedUrl {
  url: string;
  fileName: string;
  key: string;
  expiresAt: string;
}

interface PresignedUrlResponse {
  generatePresignedUrls: PresignedUrl[];
}

export function usePresignedUrl() {
  return useMutation({
    mutationFn: async (input: PresignedUrlInput) => {
      const response = await graphqlMutation<PresignedUrlResponse>(
        GENERATE_PRESIGNED_URLS,
        { projectId: input.projectId, files: input.files }
      );
      return response.generatePresignedUrls;
    },
    onError: (error: unknown) => {
      // Extract user-friendly error message
      let errorMessage = 'Failed to generate upload URLs';
      
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null) {
        const err = error as { response?: { errors?: Array<{ message?: string }> }; message?: string };
        errorMessage = err.response?.errors?.[0]?.message || err.message || errorMessage;
      }
      
      // Show concise error notification
      toast.error(errorMessage);
      
      // Log full error for debugging
      console.error('Presigned URL generation error:', error);
    },
  });
}