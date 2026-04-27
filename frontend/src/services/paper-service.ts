/**
 * 论文精读服务
 */

// 统一 API 基础地址
import API_BASE_URL from '../config';

const API_BASE = API_BASE_URL;

// 论文精读事件类型
export interface PaperReaderEvent {
  type: 'reading_start' | 'reading_continue' | 'agent_start' | 'agent_end' | 'agent_thinking' |
        'agent_output_start' | 'agent_output_chunk' | 'agent_output_end' |
        'agent_complete' | 'agent_skipped' | 'agent_error' | 'planner_decision' | 'planner_routing' |
        'reading_complete' | 'chat_response_start' | 'chat_response_chunk' |
        'chat_response_end' | 'conversation_id' | 'continue_info' | 'done' | 'error';
  agent?: string;
  description?: string;
  content?: string;
  paper_name?: string;
  paper_metadata?: PaperMetadata;
  plan?: string[];
  next_agent?: string;
  final_output?: string;
  elapsed_time?: number;
  error?: string;
  result?: any;
  conversation_id?: string;
  completed_agents?: string[];
  partial?: boolean;  // 标记是否部分完成
}

// 论文元信息
export interface PaperMetadata {
  title: string;
  authors: string[];
  affiliations?: string[];
  abstract: string;
  keywords?: string[];
  type?: string;
}

// Agent输出
export interface AgentOutput {
  agent: string;
  content: string;
  status: 'pending' | 'running' | 'done';
  error?: string;  // 错误信息
}

// 精读上下文（用于问答）
export interface ReadingContext {
  structure?: any;
  methodology?: any;
  critique?: any;
  summary?: string;
}

export const paperService = {
  /**
   * 流式执行论文精读
   */
  async readPaperStream(
    images: string[],
    paperName: string,
    conversationId: string,
    onEvent: (event: PaperReaderEvent) => void
  ): Promise<void> {
    const token = localStorage.getItem('imem_token');

    const response = await fetch(`${API_BASE}/paper/read/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        images,
        paper_name: paperName,
        conversation_id: conversationId
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const eventData = JSON.parse(line.slice(6));
            onEvent(eventData);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },

  /**
   * 论文问答（精读完成后的多轮对话）
   */
  async chatAboutPaperStream(
    question: string,
    images: string[],
    paperMetadata: PaperMetadata,
    context: ReadingContext,
    conversationId: string,
    onEvent: (event: PaperReaderEvent) => void
  ): Promise<void> {
    const token = localStorage.getItem('imem_token');

    const response = await fetch(`${API_BASE}/paper/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        question,
        images,
        paper_metadata: paperMetadata,
        context,
        conversation_id: conversationId
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const eventData = JSON.parse(line.slice(6));
            onEvent(eventData);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },

  /**
   * 从断点继续精读
   */
  async continuePaperStream(
    images: string[],
    paperName: string,
    conversationId: string,
    onEvent: (event: PaperReaderEvent) => void
  ): Promise<void> {
    const token = localStorage.getItem('imem_token');

    const response = await fetch(`${API_BASE}/paper/read/continue`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        images,
        paper_name: paperName,
        conversation_id: conversationId
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const eventData = JSON.parse(line.slice(6));
            onEvent(eventData);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },

  /**
   * 上传PDF并转换为图片
   * @param conversationId 可选，传入则会将 PDF 保存到 MinIO
   */
  async uploadPdfAsImages(
    file: File,
    maxPages?: number,
    dpi: number = 150,
    conversationId?: string
  ): Promise<{ images: { page: number; base64: string }[]; totalPages: number; pdfObjectKey?: string }> {
    const token = localStorage.getItem('imem_token');
    const formData = new FormData();
    formData.append('file', file);
    if (maxPages !== undefined) {
      formData.append('max_pages', maxPages.toString());
    }
    formData.append('dpi', dpi.toString());
    if (conversationId) {
      formData.append('conversation_id', conversationId);
    }

    const response = await fetch(`${API_BASE}/file/pdf-to-images`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData
    });

    const result = await response.json();
    if (!result.success) {
      throw new Error(result.msg || 'PDF转换失败');
    }

    return {
      images: result.data.images,
      totalPages: result.data.total_pages,
      pdfObjectKey: result.data.pdf_object_key
    };
  },

  /**
   * 从 MinIO 获取论文图片（用于恢复会话）
   */
  async getPaperImages(
    conversationId: string,
    maxPages?: number,
    dpi: number = 150
  ): Promise<{ images: { page: number; base64: string }[]; totalPages: number }> {
    const token = localStorage.getItem('imem_token');
    if (!token) {
      throw new Error('请先登录');
    }

    const params = new URLSearchParams({
      dpi: dpi.toString()
    });
    if (maxPages !== undefined) {
      params.set('max_pages', maxPages.toString());
    }

    const response = await fetch(`${API_BASE}/paper/pdf/images/${conversationId}?${params}`, {
      method: 'GET',
      headers: { Authorization: `Bearer ${token}` }
    });

    const result = await response.json();
    if (!result.success) {
      throw new Error(result.msg || '获取论文图片失败');
    }

    return {
      images: result.data.images,
      totalPages: result.data.total_pages
    };
  }
};
