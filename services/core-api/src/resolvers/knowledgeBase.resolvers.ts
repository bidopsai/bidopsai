import { GraphQLContext } from '../context';
import { requireAuth, requirePermission } from '../context';
import { NotFoundError, ValidationError } from '../utils/errors';
import { PrismaClient } from '@prisma/client';

interface CreateKnowledgeBaseInput {
  name: string;
  description?: string;
  scope: string;
  projectId?: string;
}

interface KnowledgeBaseFilterInput {
  scope?: string;
  projectId?: string;
}

interface UploadKnowledgeBaseDocumentInput {
  knowledgeBaseId: string;
  fileName: string;
  filePath: string;
  fileType: string;
  fileSize: number;
  s3Bucket: string;
  s3Key: string;
}

export const knowledgeBaseResolvers = {
  Query: {
    /**
     * Get single knowledge base by ID
     */
    knowledgeBase: async (_: any, { id }: { id: string }, context: GraphQLContext) => {
      const { prisma } = context;
      requireAuth(context);

      const kb = await prisma.knowledgeBase.findUnique({
        where: { id },
        include: {
          project: true,
          creator: true,
          documents: {
            include: {
              uploader: true,
            },
            orderBy: { uploadedAt: 'desc' },
          },
          permissions: {
            include: {
              user: true,
              role: true,
            },
          },
        },
      });

      if (!kb) {
        throw new NotFoundError('Knowledge base', id);
      }

      return kb;
    },

    /**
     * Get paginated knowledge bases with filters
     */
    knowledgeBases: async (
      _: any,
      {
        first = 10,
        after,
        filter,
      }: {
        first?: number;
        after?: string;
        filter?: KnowledgeBaseFilterInput;
      },
      context: GraphQLContext
    ) => {
      const { prisma } = context;
      requireAuth(context);

      const where: any = {};

      if (filter?.scope) {
        where.scope = filter.scope;
      }

      if (filter?.projectId) {
        where.projectId = filter.projectId;
      }

      const cursor = after ? { id: after } : undefined;

      const kbs = await prisma.knowledgeBase.findMany({
        where,
        take: first + 1,
        cursor,
        skip: cursor ? 1 : 0,
        orderBy: { createdAt: 'desc' },
        include: {
          project: true,
          creator: true,
        },
      });

      const hasNextPage = kbs.length > first;
      const nodes = hasNextPage ? kbs.slice(0, -1) : kbs;

      const edges = nodes.map((kb: any) => ({
        node: kb,
        cursor: kb.id,
      }));

      const totalCount = await prisma.knowledgeBase.count({ where });

      return {
        edges,
        pageInfo: {
          hasNextPage,
          hasPreviousPage: !!after,
          startCursor: edges[0]?.cursor,
          endCursor: edges[edges.length - 1]?.cursor,
        },
        totalCount,
      };
    },

    /**
     * Get all global knowledge bases
     */
    globalKnowledgeBases: async (_: any, __: any, context: GraphQLContext) => {
      const { prisma } = context;
      requireAuth(context);

      return prisma.knowledgeBase.findMany({
        where: { scope: 'GLOBAL' },
        include: {
          creator: true,
        },
        orderBy: { name: 'asc' },
      });
    },
  },

  Mutation: {
    /**
     * Create new knowledge base
     */
    createKnowledgeBase: async (
      _: any,
      { input }: { input: CreateKnowledgeBaseInput },
      context: GraphQLContext
    ) => {
      const { prisma, user, logger } = context;
      requireAuth(context);
      requirePermission(context, 'KNOWLEDGE_BASE', 'CREATE');

      if (!input.name || !input.scope) {
        throw new ValidationError('Missing required fields', {
          name: !input.name ? 'Name is required' : '',
          scope: !input.scope ? 'Scope is required' : '',
        });
      }

      // If project-scoped, validate project exists
      if (input.scope === 'PROJECT' && !input.projectId) {
        throw new ValidationError('Project ID required for project-scoped KB', {
          projectId: 'Project ID is required for PROJECT scope',
        });
      }

      const kb = await prisma.knowledgeBase.create({
        data: {
          name: input.name,
          description: input.description,
          scope: input.scope,
          projectId: input.projectId,
          documentCount: 0,
          createdBy: user!.id,
          // TODO: Phase 6 - Create Bedrock vector store and set vectorStoreId
        },
        include: {
          project: true,
          creator: true,
        },
      });

      logger.info(`Knowledge base created: ${kb.id}`);

      return kb;
    },

    /**
     * Update knowledge base
     */
    updateKnowledgeBase: async (
      _: any,
      {
        id,
        name,
        description,
      }: {
        id: string;
        name?: string;
        description?: string;
      },
      context: GraphQLContext
    ) => {
      const { prisma, logger } = context;
      requireAuth(context);
      requirePermission(context, 'KNOWLEDGE_BASE', 'UPDATE');

      const kb = await prisma.knowledgeBase.findUnique({ where: { id } });

      if (!kb) {
        throw new NotFoundError('Knowledge base', id);
      }

      const updated = await prisma.knowledgeBase.update({
        where: { id },
        data: {
          name,
          description,
          updatedAt: new Date(),
        },
      });

      logger.info(`Knowledge base updated: ${id}`);

      return updated;
    },

    /**
     * Delete knowledge base
     */
    deleteKnowledgeBase: async (_: any, { id }: { id: string }, context: GraphQLContext) => {
      const { prisma, logger } = context;
      requireAuth(context);
      requirePermission(context, 'KNOWLEDGE_BASE', 'DELETE');

      const kb = await prisma.knowledgeBase.findUnique({ where: { id } });

      if (!kb) {
        throw new NotFoundError('Knowledge base', id);
      }

      // TODO: Phase 6 - Delete Bedrock vector store
      // await deleteBedrockVectorStore(kb.vectorStoreId);

      await prisma.knowledgeBase.delete({ where: { id } });

      logger.info(`Knowledge base deleted: ${id}`);

      return true;
    },

    /**
     * Upload document to knowledge base
     */
    uploadKnowledgeBaseDocument: async (
      _: any,
      { input }: { input: UploadKnowledgeBaseDocumentInput },
      context: GraphQLContext
    ) => {
      const { prisma, user, logger } = context;
      requireAuth(context);

      const kb = await prisma.knowledgeBase.findUnique({
        where: { id: input.knowledgeBaseId },
      });

      if (!kb) {
        throw new NotFoundError('Knowledge base', input.knowledgeBaseId);
      }

      const document = await prisma.$transaction(async (tx: PrismaClient) => {
        // Create document record
        const doc = await tx.knowledgeBaseDocument.create({
          data: {
            knowledgeBaseId: input.knowledgeBaseId,
            fileName: input.fileName,
            filePath: input.filePath,
            fileType: input.fileType,
            fileSize: input.fileSize,
            s3Bucket: input.s3Bucket,
            s3Key: input.s3Key,
            uploadedBy: user!.id,
          },
          include: {
            uploader: true,
          },
        });

        // Increment document count
        await tx.knowledgeBase.update({
          where: { id: input.knowledgeBaseId },
          data: {
            documentCount: { increment: 1 },
          },
        });

        return doc;
      });

      logger.info(`Document uploaded to KB ${input.knowledgeBaseId}: ${document.id}`);

      // TODO: Phase 6 - Index document in Bedrock vector store
      // await indexInBedrockVectorStore(kb.vectorStoreId, document);

      return document;
    },

    /**
     * Delete knowledge base document
     */
    deleteKnowledgeBaseDocument: async (
      _: any,
      { id }: { id: string },
      context: GraphQLContext
    ) => {
      const { prisma, logger } = context;
      requireAuth(context);
      requirePermission(context, 'KNOWLEDGE_BASE', 'UPDATE');

      const document = await prisma.knowledgeBaseDocument.findUnique({
        where: { id },
      });

      if (!document) {
        throw new NotFoundError('Knowledge base document', id);
      }

      await prisma.$transaction(async (tx: PrismaClient) => {
        // Delete document
        await tx.knowledgeBaseDocument.delete({ where: { id } });

        // Decrement document count
        await tx.knowledgeBase.update({
          where: { id: document.knowledgeBaseId },
          data: {
            documentCount: { decrement: 1 },
          },
        });
      });

      logger.info(`Document deleted from KB: ${id}`);

      // TODO: Phase 6 - Remove from Bedrock vector store
      // await removeFromBedrockVectorStore(document.vectorIds);

      return true;
    },
  },

  // Field resolvers
  KnowledgeBase: {
    project: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.project) return parent.project;
      if (!parent.projectId) return null;
      return context.prisma.project.findUnique({ where: { id: parent.projectId } });
    },

    createdBy: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.creator) return parent.creator;
      return context.prisma.user.findUnique({ where: { id: parent.createdBy } });
    },

    documents: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.documents) return parent.documents;
      return context.prisma.knowledgeBaseDocument.findMany({
        where: { knowledgeBaseId: parent.id },
        orderBy: { uploadedAt: 'desc' },
      });
    },

    permissions: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.permissions) return parent.permissions;
      return context.prisma.knowledgeBasePermission.findMany({
        where: { knowledgeBaseId: parent.id },
      });
    },
  },

  KnowledgeBaseDocument: {
    fileSize: (parent: any) => {
      // Convert BigInt to number for GraphQL Int type
      return typeof parent.fileSize === 'bigint'
        ? Number(parent.fileSize)
        : parent.fileSize;
    },

    uploadedBy: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.uploader) return parent.uploader;
      return context.prisma.user.findUnique({ where: { id: parent.uploadedBy } });
    },
  },
};