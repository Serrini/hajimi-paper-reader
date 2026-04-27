/**
 * 会话管理服务
 */
import { authAxios } from './auth-service';

export interface Conversation {
  id: string;
  title: string;
  conversation_type: 'chat' | 'agent' | 'paper_reader';
  created_at: string;
  updated_at: string;
  last_message?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  message_type: 'text' | 'tool_call' | 'tool_result' | 'paper_result' | 'agent_output';
  tool_name?: string;
  tool_result?: string;
  created_at: string;
}

/**
 * 获取会话列表
 */
export const getConversations = async (type?: string, limit: number = 50): Promise<Conversation[]> => {
  try {
    const params: Record<string, any> = { limit };
    if (type) {
      params.type = type;
    }
    const response = await authAxios.get('/conversations', { params });
    return response.data?.success ? response.data.data : [];
  } catch (error) {
    console.error('获取会话列表失败:', error);
    return [];
  }
};

/**
 * 删除会话
 */
export const deleteConversation = async (
  conversationId: string
): Promise<{ success: boolean; msg?: string }> => {
  const response = await authAxios.delete(`/conversations/${conversationId}`);
  return response.data;
};

/**
 * 获取会话消息
 */
export const getMessages = async (conversationId: string, limit: number = 100): Promise<Message[]> => {
  const response = await authAxios.get(`/conversations/${conversationId}/messages`, {
    params: { limit },
  });
  return response.data.success ? response.data.data : [];
};

export default {
  getConversations,
  deleteConversation,
  getMessages,
};
