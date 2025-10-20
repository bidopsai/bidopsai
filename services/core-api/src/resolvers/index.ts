/**
 * GraphQL Resolvers - Main Export
 * 
 * Aggregates all resolver modules and exports them for Apollo Server.
 */

import { scalarResolvers } from './scalars';
import { userResolvers } from './user.resolvers';
import { projectResolvers } from './project.resolvers';
import { artifactResolvers } from './artifact.resolvers';
import { knowledgeBaseResolvers } from './knowledgeBase.resolvers';
import { workflowResolvers } from './workflow.resolvers';
import { notificationResolvers } from './notification.resolvers';
import { configurationResolvers } from './configuration.resolvers';
import { statisticsResolvers } from './statistics.resolvers';
import { subscriptionResolvers } from './subscription.resolvers';

/**
 * Combined resolvers
 * Deep merge all resolver objects
 */
export const resolvers = {
  ...scalarResolvers,
  Query: {
    ...userResolvers.Query,
    ...projectResolvers.Query,
    ...artifactResolvers.Query,
    ...knowledgeBaseResolvers.Query,
    ...workflowResolvers.Query,
    ...notificationResolvers.Query,
    ...configurationResolvers.Query,
    ...statisticsResolvers.Query,
  },
  Mutation: {
    ...userResolvers.Mutation,
    ...projectResolvers.Mutation,
    ...artifactResolvers.Mutation,
    ...knowledgeBaseResolvers.Mutation,
    ...notificationResolvers.Mutation,
    ...configurationResolvers.Mutation,
  },
  Subscription: {
    ...subscriptionResolvers.Subscription,
    ...projectResolvers.Subscription,
    ...workflowResolvers.Subscription,
    ...notificationResolvers.Subscription,
    ...artifactResolvers.Subscription,
  },
  // Type-specific field resolvers
  User: userResolvers.User,
  Role: userResolvers.Role,
  Project: projectResolvers.Project,
  ProjectDocument: projectResolvers.ProjectDocument,
  ProjectMember: projectResolvers.ProjectMember,
  Artifact: artifactResolvers.Artifact,
  ArtifactVersion: artifactResolvers.ArtifactVersion,
  KnowledgeBase: knowledgeBaseResolvers.KnowledgeBase,
  KnowledgeBaseDocument: knowledgeBaseResolvers.KnowledgeBaseDocument,
  WorkflowExecution: workflowResolvers.WorkflowExecution,
  AgentTask: workflowResolvers.AgentTask,
  AgentConfiguration: configurationResolvers.AgentConfiguration,
  Integration: configurationResolvers.Integration,
};