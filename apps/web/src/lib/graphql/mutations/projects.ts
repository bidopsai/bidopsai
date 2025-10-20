/**
 * GraphQL Mutations for Projects
 * 
 * @module lib/graphql/mutations/projects
 */

import { gql } from 'graphql-request';
import { PROJECT_FULL_DETAILS } from '../queries/projects';

/**
 * Mutation to create a new project
 */
export const CREATE_PROJECT = gql`
  ${PROJECT_FULL_DETAILS}
  mutation CreateProject($input: CreateProjectInput!) {
    createProject(input: $input) {
      ...ProjectFullDetails
    }
  }
`;

/**
 * Mutation to update a project
 */
export const UPDATE_PROJECT = gql`
  ${PROJECT_FULL_DETAILS}
  mutation UpdateProject($id: UUID!, $input: UpdateProjectInput!) {
    updateProject(id: $id, input: $input) {
      ...ProjectFullDetails
    }
  }
`;

/**
 * Mutation to delete a project
 */
export const DELETE_PROJECT = gql`
  mutation DeleteProject($id: UUID!) {
    deleteProject(id: $id)
  }
`;

/**
 * Mutation to add a member to a project
 */
export const ADD_PROJECT_MEMBER = gql`
  mutation AddProjectMember($projectId: UUID!, $userId: UUID!) {
    addProjectMember(projectId: $projectId, userId: $userId) {
      id
      joinedAt
      user {
        id
        firstName
        lastName
        email
        profileImageUrl
        roles {
          id
          name
        }
      }
      addedBy {
        id
        firstName
        lastName
      }
    }
  }
`;

/**
 * Mutation to remove a member from a project
 */
export const REMOVE_PROJECT_MEMBER = gql`
  mutation RemoveProjectMember($projectId: UUID!, $userId: UUID!) {
    removeProjectMember(projectId: $projectId, userId: $userId)
  }
`;

/**
 * Mutation to create a project document
 */
export const CREATE_PROJECT_DOCUMENT = gql`
  mutation CreateProjectDocument($input: CreateProjectDocumentInput!) {
    createProjectDocument(input: $input) {
      id
      projectId
      fileName
      filePath
      fileType
      fileSize
      rawFileLocation
      processedFileLocation
      uploadedAt
      metadata
      uploadedBy {
        id
        firstName
        lastName
      }
    }
  }
`;

/**
 * Mutation to update a project document
 */
export const UPDATE_PROJECT_DOCUMENT = gql`
  mutation UpdateProjectDocument(
    $id: UUID!
    $input: UpdateProjectDocumentInput!
  ) {
    updateProjectDocument(id: $id, input: $input) {
      id
      projectId
      fileName
      filePath
      fileType
      fileSize
      rawFileLocation
      processedFileLocation
      uploadedAt
      metadata
      uploadedBy {
        id
        firstName
        lastName
      }
    }
  }
`;

/**
 * Mutation to delete a project document
 */
export const DELETE_PROJECT_DOCUMENT = gql`
  mutation DeleteProjectDocument($id: UUID!) {
    deleteProjectDocument(id: $id)
  }
`;

/**
 * Mutation to generate presigned URLs for S3 uploads
 */
export const GENERATE_PRESIGNED_URLS = gql`
  mutation GeneratePresignedUrls(
    $projectId: UUID!
    $files: [PresignedUrlRequest!]!
  ) {
    generatePresignedUrls(projectId: $projectId, files: $files) {
      url
      fileName
      key
      expiresAt
    }
  }
`;

/**
 * Mutation to create a knowledge base
 */
export const CREATE_KNOWLEDGE_BASE = gql`
  mutation CreateKnowledgeBase($input: CreateKnowledgeBaseInput!) {
    createKnowledgeBase(input: $input) {
      id
      name
      description
      scope
      documentCount
      vectorStoreId
      createdAt
      updatedAt
      createdBy {
        id
        firstName
        lastName
      }
      project {
        id
        name
      }
    }
  }
`;

/**
 * Mutation to update a knowledge base
 */
export const UPDATE_KNOWLEDGE_BASE = gql`
  mutation UpdateKnowledgeBase(
    $id: UUID!
    $name: String
    $description: String
  ) {
    updateKnowledgeBase(id: $id, name: $name, description: $description) {
      id
      name
      description
      scope
      documentCount
      updatedAt
    }
  }
`;

/**
 * Mutation to delete a knowledge base
 */
export const DELETE_KNOWLEDGE_BASE = gql`
  mutation DeleteKnowledgeBase($id: UUID!) {
    deleteKnowledgeBase(id: $id)
  }
`;

/**
 * Mutation to upload a document to knowledge base
 */
export const UPLOAD_KNOWLEDGE_BASE_DOCUMENT = gql`
  mutation UploadKnowledgeBaseDocument(
    $input: UploadKnowledgeBaseDocumentInput!
  ) {
    uploadKnowledgeBaseDocument(input: $input) {
      id
      knowledgeBaseId
      fileName
      filePath
      fileType
      fileSize
      s3Bucket
      s3Key
      uploadedAt
      metadata
      vectorIds
      uploadedBy {
        id
        firstName
        lastName
      }
    }
  }
`;

/**
 * Mutation to delete a knowledge base document
 */
export const DELETE_KNOWLEDGE_BASE_DOCUMENT = gql`
  mutation DeleteKnowledgeBaseDocument($id: UUID!) {
    deleteKnowledgeBaseDocument(id: $id)
  }
`;

/**
 * Mutation to create a user
 */
export const CREATE_USER = gql`
  mutation CreateUser($input: CreateUserInput!) {
    createUser(input: $input) {
      id
      email
      username
      firstName
      lastName
      profileImageUrl
      emailVerified
      cognitoUserId
      createdAt
      roles {
        id
        name
        description
      }
    }
  }
`;

/**
 * Mutation to update a user
 */
export const UPDATE_USER = gql`
  mutation UpdateUser($id: UUID!, $input: UpdateUserInput!) {
    updateUser(id: $id, input: $input) {
      id
      email
      username
      firstName
      lastName
      profileImageUrl
      preferredLanguage
      themePreference
      updatedAt
    }
  }
`;

/**
 * Mutation to delete a user
 */
export const DELETE_USER = gql`
  mutation DeleteUser($id: UUID!) {
    deleteUser(id: $id)
  }
`;

/**
 * Mutation to assign a role to a user
 */
export const ASSIGN_ROLE = gql`
  mutation AssignRole($userId: UUID!, $roleId: UUID!) {
    assignRole(userId: $userId, roleId: $roleId) {
      id
      userId
      roleId
      assignedAt
      assignedBy
    }
  }
`;

/**
 * Mutation to remove a role from a user
 */
export const REMOVE_ROLE = gql`
  mutation RemoveRole($userId: UUID!, $roleId: UUID!) {
    removeRole(userId: $userId, roleId: $roleId)
  }
`;

/**
 * Mutation to update current user's profile
 */
export const UPDATE_MY_PROFILE = gql`
  mutation UpdateMyProfile($input: UpdateUserInput!) {
    updateMyProfile(input: $input) {
      id
      email
      username
      firstName
      lastName
      profileImageUrl
      preferredLanguage
      themePreference
      updatedAt
    }
  }
`;

/**
 * Mutation to mark a notification as read
 */
export const MARK_NOTIFICATION_AS_READ = gql`
  mutation MarkNotificationAsRead($id: UUID!) {
    markNotificationAsRead(id: $id) {
      id
      read
      readAt
    }
  }
`;

/**
 * Mutation to mark all notifications as read
 */
export const MARK_ALL_NOTIFICATIONS_AS_READ = gql`
  mutation MarkAllNotificationsAsRead {
    markAllNotificationsAsRead
  }
`;

/**
 * Mutation to delete a notification
 */
export const DELETE_NOTIFICATION = gql`
  mutation DeleteNotification($id: UUID!) {
    deleteNotification(id: $id)
  }
`;

/**
 * Mutation to update system settings
 */
export const UPDATE_SYSTEM_SETTINGS = gql`
  mutation UpdateSystemSettings($settings: JSON!) {
    updateSystemSettings(settings: $settings)
  }
`;