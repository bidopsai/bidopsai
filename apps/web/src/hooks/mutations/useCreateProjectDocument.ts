import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { graphqlMutation } from '@/lib/graphql/client';
import { CREATE_PROJECT_DOCUMENT } from '@/lib/graphql/mutations/projects';

interface CreateProjectDocumentInput {
  projectId: string;
  fileName: string;
  filePath: string;
  fileType: string;
  fileSize: number;
  rawFileLocation: string;
}

interface CreateProjectDocumentResponse {
  createProjectDocument: {
    id: string;
    projectId: string;
    fileName: string;
    filePath: string;
    fileType: string;
    fileSize: number;
    rawFileLocation: string;
    processedFileLocation?: string;
    uploadedAt: string;
    metadata?: Record<string, unknown>;
    uploadedBy: {
      id: string;
      firstName: string;
      lastName: string;
    };
  };
}

/**
 * Hook to create project document records in the database
 * This should be called after successfully uploading files to S3
 */
export function useCreateProjectDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: CreateProjectDocumentInput) => {
      const response = await graphqlMutation<CreateProjectDocumentResponse>(
        CREATE_PROJECT_DOCUMENT,
        { input }
      );
      return response.createProjectDocument;
    },
    onSuccess: (data) => {
      // Invalidate project queries to refetch with new document
      queryClient.invalidateQueries({ 
        queryKey: ['project', data.projectId] 
      });
      queryClient.invalidateQueries({ 
        queryKey: ['projectDocuments', data.projectId] 
      });
    },
    onError: (error: Error) => {
      console.error('Failed to create project document record:', error);
      toast.error(`Failed to save document metadata: ${error.message}`);
    },
  });
}