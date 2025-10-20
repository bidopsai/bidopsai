/**
 * GraphQL Core Type Definitions
 */

export const typeTypeDefs = `#graphql
  # ====================
  # Core Types
  # ====================
  
  type User {
    id: UUID!
    email: String!
    username: String!
    firstName: String!
    lastName: String!
    profileImageUrl: String
    preferredLanguage: String
    themePreference: String
    emailVerified: Boolean!
    createdAt: DateTime!
    updatedAt: DateTime!
    lastLogin: DateTime
    cognitoUserId: String!
    roles: [Role!]!
    projects: [ProjectMember!]!
  }
  
  type Role {
    id: UUID!
    name: String!
    description: String
    permissions: [Permission!]!
    createdAt: DateTime!
    updatedAt: DateTime!
  }
  
  type Permission {
    id: UUID!
    resource: String!
    action: String!
    createdAt: DateTime!
  }
  
  type Project {
    id: UUID!
    name: String!
    description: String
    status: ProjectStatus!
    value: Decimal
    deadline: Date
    progressPercentage: Int!
    createdBy: User!
    completedBy: User
    createdAt: DateTime!
    updatedAt: DateTime!
    completedAt: DateTime
    metadata: JSON
    documents: [ProjectDocument!]!
    members: [ProjectMember!]!
    knowledgeBases: [KnowledgeBase!]!
    artifacts: [Artifact!]!
    workflowExecutions: [WorkflowExecution!]!
  }
  
  type ProjectDocument {
    id: UUID!
    projectId: UUID!
    fileName: String!
    filePath: String!
    fileType: String!
    fileSize: Int!
    rawFileLocation: String!
    processedFileLocation: String
    uploadedBy: User!
    uploadedAt: DateTime!
    metadata: JSON
  }
  
  type ProjectMember {
    id: UUID!
    project: Project!
    user: User!
    addedBy: User!
    joinedAt: DateTime!
  }
  
  type WorkflowExecution {
    id: UUID!
    projectId: UUID!
    status: WorkflowStatus!
    initiatedBy: User!
    handledBy: User
    completedBy: User
    startedAt: DateTime!
    completedAt: DateTime
    lastUpdatedAt: DateTime!
    workflowConfig: JSON
    errorLog: JSON
    errorMessage: String
    results: JSON
    agentTasks: [AgentTask!]!
  }
  
  type AgentTask {
    id: UUID!
    workflowExecutionId: UUID!
    initiatedBy: User!
    handledBy: User
    completedBy: User
    agent: AgentType!
    status: WorkflowStatus!
    sequenceOrder: Int!
    inputData: JSON
    outputData: JSON
    taskConfig: JSON
    errorLog: JSON
    errorMessage: String
    startedAt: DateTime
    completedAt: DateTime
    executionTimeSeconds: Float
  }
  
  type Artifact {
    id: UUID!
    projectId: UUID!
    name: String!
    type: ArtifactType!
    category: ArtifactCategory!
    status: ArtifactStatus!
    createdBy: User!
    approvedBy: User
    createdAt: DateTime!
    approvedAt: DateTime
    versions: [ArtifactVersion!]!
    latestVersion: ArtifactVersion
  }
  
  type ArtifactVersion {
    id: UUID!
    artifactId: UUID!
    versionNumber: Int!
    content: JSON!
    location: String
    createdBy: User!
    createdAt: DateTime!
  }
  
  type KnowledgeBase {
    id: UUID!
    name: String!
    description: String
    scope: KnowledgeBaseScope!
    project: Project
    documentCount: Int!
    createdBy: User!
    createdAt: DateTime!
    updatedAt: DateTime!
    vectorStoreId: String
    documents: [KnowledgeBaseDocument!]!
    permissions: [KnowledgeBasePermission!]!
  }
  
  type KnowledgeBaseDocument {
    id: UUID!
    knowledgeBaseId: UUID!
    fileName: String!
    filePath: String!
    fileType: String!
    fileSize: Int!
    s3Bucket: String!
    s3Key: String!
    uploadedBy: User!
    uploadedAt: DateTime!
    metadata: JSON
  }
  
  type KnowledgeBasePermission {
    id: UUID!
    knowledgeBase: KnowledgeBase!
    user: User
    role: Role
    permissionType: String!
    grantedAt: DateTime!
  }
  
  type Notification {
    id: UUID!
    userId: UUID!
    type: NotificationType!
    title: String!
    message: String!
    read: Boolean!
    metadata: JSON
    createdAt: DateTime!
    readAt: DateTime
  }
  
  type AuditLog {
    id: UUID!
    userId: UUID!
    action: String!
    resourceType: String!
    resourceId: UUID!
    previousState: JSON
    newState: JSON
    ipAddress: String
    userAgent: String
    createdAt: DateTime!
  }
  
  type AgentConfiguration {
    id: UUID!
    agentType: AgentType!
    modelName: String!
    temperature: Float!
    maxTokens: Int!
    systemPrompt: JSON!
    additionalParameters: JSON
    enabled: Boolean!
    createdAt: DateTime!
    updatedAt: DateTime!
    updatedBy: User
  }
  
  type Integration {
    id: UUID!
    type: IntegrationType!
    name: String!
    configuration: JSON!
    enabled: Boolean!
    createdBy: User!
    createdAt: DateTime!
    updatedAt: DateTime!
    logs: [IntegrationLog!]!
  }
  
  type IntegrationLog {
    id: UUID!
    action: String!
    status: String!
    requestData: JSON
    responseData: JSON
    errorMessage: String
    createdAt: DateTime!
  }
  
  type BidStatistics {
    id: UUID!
    periodStart: Date!
    periodEnd: Date!
    submittedBids: Int!
    wonBids: Int!
    totalValue: Decimal!
    wonValue: Decimal!
    successRate: Float!
    activeRfps: Int!
    detailedMetrics: JSON
    calculatedAt: DateTime!
  }
  
  type PresignedUrl {
    url: String!
    fileName: String!
    key: String!
    expiresAt: DateTime!
  }
  
  # ====================
  # Pagination Types
  # ====================
  
  type PageInfo {
    hasNextPage: Boolean!
    hasPreviousPage: Boolean!
    startCursor: String
    endCursor: String
  }
  
  type UserEdge {
    node: User!
    cursor: String!
  }
  
  type UserConnection {
    edges: [UserEdge!]!
    pageInfo: PageInfo!
    totalCount: Int!
  }
  
  type ProjectEdge {
    node: Project!
    cursor: String!
  }
  
  type ProjectConnection {
    edges: [ProjectEdge!]!
    pageInfo: PageInfo!
    totalCount: Int!
  }
  
  type KnowledgeBaseEdge {
    node: KnowledgeBase!
    cursor: String!
  }
  
  type KnowledgeBaseConnection {
    edges: [KnowledgeBaseEdge!]!
    pageInfo: PageInfo!
    totalCount: Int!
  }
`;