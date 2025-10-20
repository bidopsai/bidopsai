import { GraphQLContext } from '../context';
import {
  requireAuth,
  requirePermission,
  requireOwnership,
  hasRole,
} from '../context';
import {
  ValidationError,
  NotFoundError,
  ConflictError,
  AuthorizationError,
  ErrorCode,
} from '../utils/errors';
import { PrismaClient } from '@prisma/client';

interface CreateProjectInput {
  name: string;
  description?: string;
  deadline?: string;
  value?: number;
  knowledgeBaseIds?: string[];
  memberIds?: string[];
}

interface UpdateProjectInput {
  name?: string;
  description?: string;
  status?: string;
  value?: number;
  deadline?: string;
}

interface ProjectFilterInput {
  status?: string;
  createdBy?: string;
  dateFrom?: string;
  dateTo?: string;
}

interface PresignedUrlRequest {
  fileName: string;
  fileType: string;
  fileSize: number;
}

interface CreateProjectDocumentInput {
  projectId: string;
  fileName: string;
  filePath: string;
  fileType: string;
  fileSize: number;
  rawFileLocation: string;
}

interface UpdateProjectDocumentInput {
  processedFileLocation?: string;
  metadata?: any;
}

export const projectResolvers = {
  Query: {
    /**
     * Get single project by ID
     */
    project: async (_: any, { id }: { id: string }, context: GraphQLContext) => {
      const { prisma } = context;
      requireAuth(context);

      const project = await prisma.project.findUnique({
        where: { id },
        include: {
          creator: true,
          completer: true,
          documents: {
            include: {
              uploader: true,
            },
            orderBy: { uploadedAt: 'desc' },
          },
          members: {
            include: {
              user: true,
              addedBy: true,
            },
          },
          knowledgeBases: true,
          artifacts: {
            include: {
              creator: true,
            },
            orderBy: { createdAt: 'desc' },
          },
          workflowExecutions: {
            orderBy: { startedAt: 'desc' },
            take: 10, // Limit to recent 10 workflows
          },
        },
      });

      if (!project) {
        throw new NotFoundError('Project', id);
      }

      // Check access: project owner, member, or admin
      const isOwner = project.createdBy === context.user!.id;
      const isMember = project.members.some((m: any) => m.userId === context.user!.id);
      const isAdmin = hasRole(context, 'ADMIN');

      if (!isOwner && !isMember && !isAdmin) {
        throw new AuthorizationError('You do not have access to this project');
      }

      return project;
    },

    /**
     * Get paginated projects list with filters
     */
    projects: async (
      _: any,
      {
        first = 10,
        after,
        filter,
      }: {
        first?: number;
        after?: string;
        filter?: ProjectFilterInput;
      },
      context: GraphQLContext
    ) => {
      const { prisma } = context;
      requireAuth(context);
      requirePermission(context, 'PROJECT', 'READ');

      // Build where clause
      const where: any = {};

      if (filter?.status) {
        where.status = filter.status;
      }

      if (filter?.createdBy) {
        where.createdBy = filter.createdBy;
      }

      if (filter?.dateFrom || filter?.dateTo) {
        where.createdAt = {};
        if (filter.dateFrom) {
          where.createdAt.gte = new Date(filter.dateFrom);
        }
        if (filter.dateTo) {
          where.createdAt.lte = new Date(filter.dateTo);
        }
      }

      // Cursor-based pagination
      const cursor = after ? { id: after } : undefined;

      const projects = await prisma.project.findMany({
        where,
        take: first + 1,
        cursor,
        skip: cursor ? 1 : 0,
        orderBy: { createdAt: 'desc' },
        include: {
          creator: true,
          members: {
            include: {
              user: true,
            },
          },
        },
      });

      const hasNextPage = projects.length > first;
      const nodes = hasNextPage ? projects.slice(0, -1) : projects;

      const edges = nodes.map((project: any) => ({
        node: project,
        cursor: project.id,
      }));

      const totalCount = await prisma.project.count({ where });

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
     * Get current user's projects
     */
    myProjects: async (
      _: any,
      {
        first = 10,
        after,
      }: {
        first?: number;
        after?: string;
      },
      context: GraphQLContext
    ) => {
      const { prisma, user } = context;
      requireAuth(context);

      // Get projects where user is owner or member
      const cursor = after ? { id: after } : undefined;

      const projects = await prisma.project.findMany({
        where: {
          OR: [
            { createdBy: user!.id },
            {
              members: {
                some: {
                  userId: user!.id,
                },
              },
            },
          ],
        },
        take: first + 1,
        cursor,
        skip: cursor ? 1 : 0,
        orderBy: { createdAt: 'desc' },
      });

      const hasNextPage = projects.length > first;
      const nodes = hasNextPage ? projects.slice(0, -1) : projects;

      const edges = nodes.map((project: any) => ({
        node: project,
        cursor: project.id,
      }));

      const totalCount = await prisma.project.count({
        where: {
          OR: [
            { createdBy: user!.id },
            {
              members: {
                some: {
                  userId: user!.id,
                },
              },
            },
          ],
        },
      });

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
  },

  Mutation: {
    /**
     * Create a new project
     */
    createProject: async (
      _: any,
      { input }: { input: CreateProjectInput },
      context: GraphQLContext
    ) => {
      const { prisma, user, logger } = context;
      requireAuth(context);
      requirePermission(context, 'PROJECT', 'CREATE');

      // Validate required fields
      if (!input.name) {
        throw new ValidationError('Project name is required', {
          name: 'Name is required',
        });
      }

      try {
        const project = await prisma.$transaction(async (tx) => {
          // Create project
          const newProject = await tx.project.create({
            data: {
              name: input.name,
              description: input.description,
              deadline: input.deadline ? new Date(input.deadline) : undefined,
              value: input.value,
              status: 'OPEN',
              progressPercentage: 0,
              createdBy: user!.id,
            },
          });

          // Add project creator as member
          await tx.projectMember.create({
            data: {
              projectId: newProject.id,
              userId: user!.id,
              addedById: user!.id,
            },
          });

          // Add additional members if provided
          if (input.memberIds && input.memberIds.length > 0) {
            await tx.projectMember.createMany({
              data: input.memberIds
                .filter((memberId) => memberId !== user!.id) // Don't duplicate creator
                .map((memberId) => ({
                  projectId: newProject.id,
                  userId: memberId,
                  addedById: user!.id,
                })),
            });
          }

          // Associate knowledge bases if provided
          // Note: Knowledge base association logic will be implemented when KB schema is finalized

          return newProject;
        });

        logger.info(`Project created: ${project.id}`);

        // Fetch complete project with relations
        return prisma.project.findUnique({
          where: { id: project.id },
          include: {
            creator: true,
            members: {
              include: {
                user: {
                  include: {
                    roles: {
                      include: {
                        role: true,
                      },
                    },
                  },
                },
                addedBy: true,
              },
            },
          },
        });
      } catch (error) {
        logger.error('Failed to create project', { error });
        throw error;
      }
    },

    /**
     * Update an existing project
     */
    updateProject: async (
      _: any,
      { id, input }: { id: string; input: UpdateProjectInput },
      context: GraphQLContext
    ) => {
      const { prisma, logger } = context;
      requireAuth(context);

      const project = await prisma.project.findUnique({
        where: { id },
      });

      if (!project) {
        throw new NotFoundError('Project', id);
      }

      // Check ownership or admin
      requireOwnership(context, project.createdBy);

      const updatedProject = await prisma.project.update({
        where: { id },
        data: {
          name: input.name,
          description: input.description,
          status: input.status,
          value: input.value,
          deadline: input.deadline ? new Date(input.deadline) : undefined,
          updatedAt: new Date(),
        },
      });

      logger.info(`Project updated: ${id}`);

      return updatedProject;
    },

    /**
     * Delete a project
     */
    deleteProject: async (_: any, { id }: { id: string }, context: GraphQLContext) => {
      const { prisma, logger } = context;
      requireAuth(context);

      const project = await prisma.project.findUnique({
        where: { id },
      });

      if (!project) {
        throw new NotFoundError('Project', id);
      }

      // Check ownership or admin
      requireOwnership(context, project.createdBy);

      // Delete project (cascade will handle related records)
      await prisma.project.delete({
        where: { id },
      });

      logger.info(`Project deleted: ${id}`);

      return true;
    },

    /**
     * Add a member to a project
     */
    addProjectMember: async (
      _: any,
      { projectId, userId }: { projectId: string; userId: string },
      context: GraphQLContext
    ) => {
      const { prisma, logger } = context;
      requireAuth(context);

      const project = await prisma.project.findUnique({
        where: { id: projectId },
      });

      if (!project) {
        throw new NotFoundError('Project', projectId);
      }

      // Check ownership or admin
      requireOwnership(context, project.createdBy);

      // Check if user exists
      const user = await prisma.user.findUnique({
        where: { id: userId },
      });

      if (!user) {
        throw new NotFoundError('User', userId);
      }

      // Check if already a member
      const existing = await prisma.projectMember.findFirst({
        where: { projectId, userId },
      });

      if (existing) {
        throw new ConflictError('User is already a project member');
      }

      const member = await prisma.projectMember.create({
        data: {
          projectId,
          userId,
          addedById: context.user!.id,
        },
        include: {
          project: true,
          user: true,
        },
      });

      logger.info(`Member added to project: ${userId} -> ${projectId}`);

      return member;
    },

    /**
     * Remove a member from a project
     */
    removeProjectMember: async (
      _: any,
      { projectId, userId }: { projectId: string; userId: string },
      context: GraphQLContext
    ) => {
      const { prisma, logger } = context;
      requireAuth(context);

      const project = await prisma.project.findUnique({
        where: { id: projectId },
      });

      if (!project) {
        throw new NotFoundError('Project', projectId);
      }

      // Check ownership or admin
      requireOwnership(context, project.createdBy);

      // Cannot remove project creator
      if (userId === project.createdBy) {
        throw new ValidationError('Cannot remove project creator', {
          userId: 'Project creator cannot be removed',
        });
      }

      const member = await prisma.projectMember.findFirst({
        where: { projectId, userId },
      });

      if (!member) {
        throw new NotFoundError('Project member');
      }

      await prisma.projectMember.delete({
        where: { id: member.id },
      });

      logger.info(`Member removed from project: ${userId} <- ${projectId}`);

      return true;
    },

    /**
     * Generate presigned URLs for S3 upload
     * TODO: Phase 6 - Implement actual S3 integration
     */
    generatePresignedUrls: async (
      _: any,
      {
        projectId,
        files,
      }: {
        projectId: string;
        files: PresignedUrlRequest[];
      },
      context: GraphQLContext
    ) => {
      const { prisma, logger, services } = context;
      requireAuth(context);

      const project = await prisma.project.findUnique({
        where: { id: projectId },
      });

      if (!project) {
        throw new NotFoundError('Project', projectId);
      }

      // Check project access
      const isMember = await prisma.projectMember.findFirst({
        where: {
          projectId,
          userId: context.user!.id,
        },
      });

      if (!isMember && project.createdBy !== context.user!.id && !hasRole(context, 'ADMIN')) {
        throw new AuthorizationError('You do not have access to this project');
      }

      // Generate actual S3 presigned URLs using S3Service
      const presignedUrls = await services.s3.generateBulkPresignedUploadUrls(
        projectId,
        files.map((file) => ({
          fileName: file.fileName,
          fileType: file.fileType,
          fileSize: file.fileSize,
        }))
      );

      logger.info(`Generated ${files.length} presigned URLs for project: ${projectId}`);

      return presignedUrls.map((url) => ({
        url: url.url,
        fileName: url.fileName,
        key: url.key,
        expiresAt: url.expiresAt.toISOString(),
      }));
    },

    /**
     * Create project document record after S3 upload
     */
    createProjectDocument: async (
      _: any,
      { input }: { input: CreateProjectDocumentInput },
      context: GraphQLContext
    ) => {
      const { prisma, logger } = context;
      requireAuth(context);

      const project = await prisma.project.findUnique({
        where: { id: input.projectId },
      });

      if (!project) {
        throw new NotFoundError('Project', input.projectId);
      }

      const document = await prisma.projectDocument.create({
        data: {
          projectId: input.projectId,
          fileName: input.fileName,
          filePath: input.filePath,
          fileType: input.fileType,
          fileSize: input.fileSize,
          rawFileLocation: input.rawFileLocation,
          uploadedBy: context.user!.id,
        },
        include: {
          uploader: true,
        },
      });

      logger.info(`Project document created: ${document.id}`);

      return document;
    },

    /**
     * Update project document (e.g., add processed file location)
     */
    updateProjectDocument: async (
      _: any,
      {
        id,
        input,
      }: {
        id: string;
        input: UpdateProjectDocumentInput;
      },
      context: GraphQLContext
    ) => {
      const { prisma, logger } = context;
      requireAuth(context);

      const document = await prisma.projectDocument.findUnique({
        where: { id },
      });

      if (!document) {
        throw new NotFoundError('Project document', id);
      }

      const updatedDocument = await prisma.projectDocument.update({
        where: { id },
        data: {
          processedFileLocation: input.processedFileLocation,
          metadata: input.metadata,
        },
      });

      logger.info(`Project document updated: ${id}`);

      return updatedDocument;
    },

    /**
     * Delete a project document
     */
    deleteProjectDocument: async (_: any, { id }: { id: string }, context: GraphQLContext) => {
      const { prisma, logger } = context;
      requireAuth(context);

      const document = await prisma.projectDocument.findUnique({
        where: { id },
        include: {
          project: true,
        },
      });

      if (!document) {
        throw new NotFoundError('Project document', id);
      }

      // Check ownership
      requireOwnership(context, document.project.createdBy);

      // TODO: Phase 6 - Delete from S3
      // await deleteFromS3(document.rawFileLocation);

      await prisma.projectDocument.delete({
        where: { id },
      });

      logger.info(`Project document deleted: ${id}`);

      return true;
    },
  },

  // Subscription for project updates
  Subscription: {
    projectUpdated: {
      subscribe: async (_: any, { projectId }: { projectId: string }, context: GraphQLContext) => {
        requireAuth(context);
        // TODO: Phase 8 - Implement subscription with PubSub
        throw new Error('Subscriptions not yet implemented');
      },
    },
  },

  // Field resolvers
  Project: {
    value: (parent: any) => {
      // Convert Prisma Decimal to number for GraphQL
      return parent.value ? Number(parent.value) : null;
    },

    createdBy: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.creator) {
        return parent.creator;
      }
      return context.prisma.user.findUnique({
        where: { id: parent.createdBy },
      });
    },

    completedBy: async (parent: any, _: any, context: GraphQLContext) => {
      if (!parent.completedBy) {
        return null;
      }
      if (parent.completer) {
        return parent.completer;
      }
      return context.prisma.user.findUnique({
        where: { id: parent.completedBy },
      });
    },

    documents: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.documents) {
        return parent.documents;
      }
      return context.prisma.projectDocument.findMany({
        where: { projectId: parent.id },
        include: {
          uploader: true,
        },
        orderBy: { uploadedAt: 'desc' },
      });
    },

    members: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.members) {
        return parent.members;
      }
      return context.prisma.projectMember.findMany({
        where: { projectId: parent.id },
        include: {
          user: true,
        },
      });
    },

    knowledgeBases: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.knowledgeBases) {
        return parent.knowledgeBases;
      }
      // TODO: Implement when KB association schema is finalized
      return [];
    },

    artifacts: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.artifacts) {
        return parent.artifacts;
      }
      return context.prisma.artifact.findMany({
        where: { projectId: parent.id },
        orderBy: { createdAt: 'desc' },
      });
    },

    workflowExecutions: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.workflowExecutions) {
        return parent.workflowExecutions;
      }
      return context.prisma.workflowExecution.findMany({
        where: { projectId: parent.id },
        orderBy: { startedAt: 'desc' },
        take: 10,
      });
    },
  },

  // ProjectDocument field resolvers
  ProjectDocument: {
    fileSize: (parent: any) => {
      // Convert BigInt to number for GraphQL Int type
      return typeof parent.fileSize === 'bigint'
        ? Number(parent.fileSize)
        : parent.fileSize;
    },

    uploadedBy: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.uploader) {
        return parent.uploader;
      }
      return context.prisma.user.findUnique({
        where: { id: parent.uploadedBy },
      });
    },
  },

  // ProjectMember field resolvers
  ProjectMember: {
    addedBy: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.addedBy) {
        return parent.addedBy;
      }
      return context.prisma.user.findUnique({
        where: { id: parent.addedById },
      });
    },

    user: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.user) {
        return parent.user;
      }
      return context.prisma.user.findUnique({
        where: { id: parent.userId },
      });
    },

    project: async (parent: any, _: any, context: GraphQLContext) => {
      if (parent.project) {
        return parent.project;
      }
      return context.prisma.project.findUnique({
        where: { id: parent.projectId },
      });
    },
  },
};