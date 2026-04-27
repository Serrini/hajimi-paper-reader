import React, { useState, useRef, useEffect } from 'react';
import {
  Card,
  Input,
  Button,
  Space,
  Steps,
  Typography,
  Tag,
  Collapse,
  message,
  Spin,
  Upload,
  List,
  Avatar,
  Image,
  Tooltip,
  Drawer,
  Empty
} from 'antd';
import {
  UploadOutlined,
  SendOutlined,
  RobotOutlined,
  UserOutlined,
  FileTextOutlined,
  SearchOutlined,
  ExperimentOutlined,
  BulbOutlined,
  EditOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  PictureOutlined,
  DeleteOutlined,
  HistoryOutlined,
  PlusOutlined,
  ReloadOutlined
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { paperService, PaperReaderEvent, PaperMetadata, AgentOutput, ReadingContext } from '../../services/paper-service';
import { getConversations, getMessages, deleteConversation, Conversation, Message } from '../../services/conversation-service';
import { useSearchParams } from 'react-router-dom';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;

// Agent 配置
const AGENTS = [
  { key: 'Planner', name: '论文解析', icon: <RobotOutlined />, color: '#722ed1' },
  { key: 'Extractor', name: '结构提取', icon: <SearchOutlined />, color: '#1890ff' },
  { key: 'Analyzer', name: '方法分析', icon: <ExperimentOutlined />, color: '#fa8c16' },
  { key: 'Critic', name: '创新点分析', icon: <BulbOutlined />, color: '#52c41a' },
  { key: 'Summarizer', name: '精读总结', icon: <EditOutlined />, color: '#eb2f96' },
];

// 消息类型
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  images?: string[];
}

const PaperReaderPage: React.FC = () => {
  // URL参数
  const [searchParams, setSearchParams] = useSearchParams();

  // 论文状态
  const [paperImages, setPaperImages] = useState<string[]>([]);
  const [paperName, setPaperName] = useState('');
  const [paperMetadata, setPaperMetadata] = useState<PaperMetadata | null>(null);

  // 精读状态
  const [isReading, setIsReading] = useState(false);
  const [isReadingComplete, setIsReadingComplete] = useState(false);
  const [isReadingInterrupted, setIsReadingInterrupted] = useState(false); // 是否中断
  const [activeAgents, setActiveAgents] = useState<Set<string>>(new Set()); // 当前运行中的agents（支持多个）
  const [agentOutputs, setAgentOutputs] = useState<Record<string, AgentOutput>>({});
  const [streamingContents, setStreamingContents] = useState<Record<string, string>>({}); // 每个agent独立的流式内容
  const [readingContext, setReadingContext] = useState<ReadingContext>({});
  const [elapsedTime, setElapsedTime] = useState<number | null>(null);
  const [activePanel, setActivePanel] = useState<string[]>([]);

  // 会话状态
  const [conversationId, setConversationId] = useState<string>('');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // 对话状态
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isChatting, setIsChatting] = useState(false);
  const [chatStreamContent, setChatStreamContent] = useState('');

  // 上传状态
  const [uploading, setUploading] = useState(false);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const streamingContentsRef = useRef<Record<string, string>>({}); // 每个agent独立的流式内容
  const chatStreamContentRef = useRef<string>('');
  const pdfFileRef = useRef<File | null>(null); // 保存原始 PDF 文件

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, chatStreamContent]);

  useEffect(() => {
    if (workspaceRef.current) {
      workspaceRef.current.scrollTop = workspaceRef.current.scrollHeight;
    }
  }, [streamingContents, agentOutputs]);

  // 页面加载时检查URL参数并恢复会话
  useEffect(() => {
    const convId = searchParams.get('conversation_id');
    if (convId) {
      restoreConversation(convId);
    }
  }, []);

  // 加载历史会话列表
  const loadConversations = async () => {
    setLoadingHistory(true);
    try {
      const list = await getConversations('paper_reader', 50);
      setConversations(list);
    } catch (error) {
      console.error('加载历史会话失败:', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  // 恢复会话
  const restoreConversation = async (convId: string) => {
    try {
      const messageList = await getMessages(convId);
      if (messageList.length === 0) {
        message.warning('会话记录为空');
        return;
      }

      setConversationId(convId);

      // 找到 paper_result 类型的消息，恢复精读结果
      const paperResultMsg = messageList.find((m: Message) => m.message_type === 'paper_result');
      if (paperResultMsg) {
        try {
          const result = JSON.parse(paperResultMsg.content);
          if (result.paper_metadata) {
            setPaperMetadata(result.paper_metadata);
            setPaperName(result.paper_metadata.title || '');
          }
          if (result.final_output) {
            setReadingContext({ summary: result.final_output });
          }
          setIsReadingComplete(true);

          // 添加系统消息
          setMessages([{
            id: 'restored',
            role: 'system',
            content: `已恢复论文精读会话: ${result.paper_metadata?.title || '未知论文'}`,
            timestamp: new Date()
          }]);
        } catch (e) {
          console.error('解析精读结果失败:', e);
        }
      }

      // 恢复 Agent 输出
      const agentOutputMsgs = messageList.filter((m: Message) => m.message_type === 'agent_output');
      let isInterrupted = false;
      if (agentOutputMsgs.length > 0) {
        const restoredOutputs: Record<string, AgentOutput> = {};
        const panels: string[] = [];
        agentOutputMsgs.forEach((m: Message) => {
          if (m.tool_name) {
            restoredOutputs[m.tool_name] = {
              agent: m.tool_name,
              content: m.content,
              status: 'done'
            };
            panels.push(m.tool_name);
          }
        });
        setAgentOutputs(restoredOutputs);
        setActivePanel(panels);

        // 检查是否有未完成的Agent（中断情况）
        const allAgents = ['Planner', 'Extractor', 'Analyzer', 'Critic', 'Summarizer'];
        const completedAgents = Object.keys(restoredOutputs);
        const hasIncomplete = completedAgents.length > 0 && completedAgents.length < allAgents.length;
        if (hasIncomplete && !paperResultMsg) {
          setIsReadingInterrupted(true);
          isInterrupted = true;
        }
      }

      // 恢复对话消息（排除 agent_output 和 paper_result）
      const chatMessages: ChatMessage[] = messageList
        .filter((m: Message) => m.message_type !== 'paper_result' && m.message_type !== 'agent_output')
        .map((m: Message) => ({
          id: m.id,
          role: m.role as 'user' | 'assistant' | 'system',
          content: m.content,
          timestamp: new Date(m.created_at)
        }));

      if (chatMessages.length > 0) {
        setMessages(prev => [...prev, ...chatMessages]);
      }

      // 尝试从 MinIO 加载论文图片
      try {
        message.loading({ content: '正在加载论文...', key: 'loadPdf' });
        const pdfResult = await paperService.getPaperImages(convId, undefined, 150);
        const images = pdfResult.images.map(img => img.base64);
        setPaperImages(images);
        message.success({ content: `论文加载成功，共${pdfResult.totalPages}页`, key: 'loadPdf' });

        // 根据恢复状态显示不同提示
        if (isInterrupted) {
          message.warning('精读未完成，可点击"继续精读"继续');
        }
      } catch (pdfError: any) {
        console.warn('加载论文图片失败:', pdfError);
        message.warning({ content: '论文图片加载失败，需重新上传', key: 'loadPdf' });
        // 根据恢复状态显示不同提示
        if (isInterrupted) {
          message.warning('会话已恢复，精读未完成。请上传论文后点击"继续精读"');
        } else {
          message.info('会话已恢复（需重新上传论文图片才能继续问答）');
        }
      }
    } catch (error) {
      console.error('恢复会话失败:', error);
      message.error('恢复会话失败');
    }
  };

  // 删除历史会话
  const handleDeleteConversation = async (convId: string) => {
    try {
      await deleteConversation(convId);
      setConversations(prev => prev.filter(c => c.id !== convId));
      message.success('删除成功');
    } catch (error) {
      message.error('删除失败');
    }
  };

  // 处理PDF上传
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      message.error('请上传PDF文件');
      return;
    }

    setUploading(true);
    try {
      // 如果已有 conversation_id，上传时同时保存到 MinIO
      const result = await paperService.uploadPdfAsImages(file, undefined, 150, conversationId || undefined);
      const images = result.images.map(img => img.base64);
      setPaperImages(images);
      setPaperName(file.name);

      // 保存原始文件，以便后续保存到 MinIO
      pdfFileRef.current = file;

      // 添加系统消息
      setMessages([{
        id: Date.now().toString(),
        role: 'system',
        content: `已上传论文: ${file.name} (共${result.totalPages}页，已转换${images.length}页)`,
        timestamp: new Date()
      }]);

      message.success(`论文上传成功，共${result.totalPages}页`);
    } catch (error: any) {
      message.error(error.message || '上传失败');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // 开始精读
  const startReading = async () => {
    if (paperImages.length === 0) {
      message.warning('请先上传论文');
      return;
    }

    setIsReading(true);
    setIsReadingComplete(false);
    setActiveAgents(new Set());
    setAgentOutputs({});
    setStreamingContents({});
    streamingContentsRef.current = {};
    setElapsedTime(null);
    setActivePanel([]);

    // 添加用户消息
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'user',
      content: '开始精读这篇论文',
      timestamp: new Date()
    }]);

    try {
      await paperService.readPaperStream(
        paperImages,
        paperName,
        '',
        handleReadingEvent
      );
    } catch (error: any) {
      message.error(error.message || '精读失败');
    } finally {
      setIsReading(false);
    }
  };

  // 继续精读（从断点恢复）
  const continueReading = async () => {
    if (paperImages.length === 0) {
      message.warning('请先上传论文图片');
      return;
    }
    if (!conversationId) {
      message.warning('缺少会话ID，请重新开始精读');
      return;
    }

    setIsReading(true);
    setIsReadingInterrupted(false);
    setStreamingContents({});
    streamingContentsRef.current = {};

    // 添加用户消息
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'user',
      content: '继续精读这篇论文',
      timestamp: new Date()
    }]);

    try {
      await paperService.continuePaperStream(
        paperImages,
        paperName,
        conversationId,
        handleReadingEvent
      );
    } catch (error: any) {
      message.error(error.message || '继续精读失败');
      setIsReadingInterrupted(true);
    } finally {
      setIsReading(false);
    }
  };

  // 处理精读事件
  const handleReadingEvent = (event: PaperReaderEvent) => {
    switch (event.type) {
      case 'conversation_id':
        // 保存会话ID并更新URL
        if (event.conversation_id) {
          setConversationId(event.conversation_id);
          setSearchParams({ conversation_id: event.conversation_id });

          // 如果有保存的 PDF 文件，上传到 MinIO
          if (pdfFileRef.current) {
            paperService.uploadPdfAsImages(pdfFileRef.current, undefined, 150, event.conversation_id)
              .then(() => {
                console.log('PDF 已保存到 MinIO');
              })
              .catch(err => {
                console.warn('保存 PDF 到 MinIO 失败:', err);
              });
          }
        }
        break;

      case 'reading_start':
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: '开始分析论文，请稍候...',
          timestamp: new Date()
        }]);
        break;

      case 'agent_start':
        if (event.agent) {
          // 添加到活跃agent集合
          setActiveAgents(prev => new Set([...prev, event.agent!]));
          // 初始化该agent的流式内容
          streamingContentsRef.current[event.agent] = '';
          setStreamingContents(prev => ({ ...prev, [event.agent!]: '' }));
          // 更新agent输出状态
          setAgentOutputs(prev => ({
            ...prev,
            [event.agent!]: {
              agent: event.agent!,
              content: '',
              status: 'running'
            }
          }));
          setActivePanel(prev => [...prev, event.agent!]);
        }
        break;

      case 'agent_thinking':
        // 显示思考过程
        break;

      case 'agent_output_start':
        // agent_output_start 现在由 agent_start 处理
        break;

      case 'agent_output_chunk':
        // 根据 agent 字段区分不同agent的输出
        if (event.agent) {
          const agentKey = event.agent;
          streamingContentsRef.current[agentKey] = (streamingContentsRef.current[agentKey] || '') + (event.content || '');
          setStreamingContents(prev => ({
            ...prev,
            [agentKey]: streamingContentsRef.current[agentKey]
          }));
        }
        break;

      case 'agent_output_end':
        if (event.agent) {
          const agentKey = event.agent;
          const finalContent = streamingContentsRef.current[agentKey] || '';
          // 更新agent输出
          setAgentOutputs(prev => ({
            ...prev,
            [agentKey]: {
              ...prev[agentKey],
              content: finalContent,
              status: 'done'
            }
          }));
          // 从活跃agent集合中移除
          setActiveAgents(prev => {
            const newSet = new Set(prev);
            newSet.delete(agentKey);
            return newSet;
          });
          // 清理该agent的流式内容
          delete streamingContentsRef.current[agentKey];
          setStreamingContents(prev => {
            const newContents = { ...prev };
            delete newContents[agentKey];
            return newContents;
          });
        }
        break;

      case 'agent_complete':
        if (event.agent) {
          setAgentOutputs(prev => ({
            ...prev,
            [event.agent!]: {
              ...prev[event.agent!],
              status: 'done'
            }
          }));
          // 保存上下文
          if (event.result) {
            setReadingContext(prev => ({ ...prev, ...event.result }));
          }
        }
        break;

      case 'agent_end':
        // Agent结束
        break;

      case 'agent_error':
        // Agent执行出错
        if (event.agent) {
          setAgentOutputs(prev => ({
            ...prev,
            [event.agent!]: {
              ...prev[event.agent!],
              status: 'done',
              error: event.error
            }
          }));
          // 从活跃agent集合中移除
          setActiveAgents(prev => {
            const newSet = new Set(prev);
            newSet.delete(event.agent!);
            return newSet;
          });
        }
        break;

      case 'planner_decision':
        if (event.paper_metadata) {
          setPaperMetadata(event.paper_metadata);
        }
        break;

      case 'reading_complete':
        setIsReadingComplete(true);
        setActiveAgents(new Set()); // 清空所有活跃agent
        setElapsedTime(event.elapsed_time || null);
        if (event.paper_metadata) {
          setPaperMetadata(event.paper_metadata);
        }
        const completeMsg = event.partial
          ? `论文精读部分完成（有错误）！耗时 ${(event.elapsed_time || 0).toFixed(1)}秒。`
          : `论文精读完成！耗时 ${(event.elapsed_time || 0).toFixed(1)}秒。\n\n你可以继续对这篇论文提问。`;
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: completeMsg,
          timestamp: new Date()
        }]);
        break;

      case 'error':
        message.error(event.error || '发生错误');
        // 检查是否有部分完成的Agent，标记为中断
        if (Object.keys(agentOutputs).length > 0 && !isReadingComplete) {
          setIsReadingInterrupted(true);
        }
        break;

      case 'reading_continue':
        // 继续精读开始
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: `继续精读论文，跳过已完成的Agent...`,
          timestamp: new Date()
        }]);
        break;

      case 'continue_info':
        // 显示已完成的Agent信息
        if (event.completed_agents && event.completed_agents.length > 0) {
          const completedList = event.completed_agents.join(', ');
          setMessages(prev => [...prev, {
            id: Date.now().toString(),
            role: 'system',
            content: `已完成的分析: ${completedList}`,
            timestamp: new Date()
          }]);
        }
        break;

      case 'agent_skipped':
        // Agent被跳过（已完成）
        if (event.agent) {
          setAgentOutputs(prev => ({
            ...prev,
            [event.agent!]: {
              ...prev[event.agent!],
              status: 'done'
            }
          }));
        }
        break;
    }
  };

  // 发送问答消息
  const sendChatMessage = async () => {
    if (!inputValue.trim()) return;
    if (!isReadingComplete) {
      message.warning('请先完成论文精读');
      return;
    }
    if (paperImages.length === 0) {
      message.warning('请先上传论文图片');
      return;
    }

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsChatting(true);
    setChatStreamContent('');
    chatStreamContentRef.current = '';

    try {
      await paperService.chatAboutPaperStream(
        inputValue,
        paperImages.slice(0, 5), // 只用前5页
        paperMetadata!,
        readingContext,
        conversationId,
        handleChatEvent
      );

      // 添加完整回复
      const finalContent = chatStreamContentRef.current;
      if (finalContent) {
        setMessages(prev => [...prev, {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: finalContent,
          timestamp: new Date()
        }]);
      }
    } catch (error: any) {
      message.error(error.message || '问答失败');
    } finally {
      setIsChatting(false);
      setChatStreamContent('');
      chatStreamContentRef.current = '';
    }
  };

  // 处理问答事件
  const handleChatEvent = (event: PaperReaderEvent) => {
    if (event.type === 'chat_response_chunk') {
      chatStreamContentRef.current += (event.content || '');
      setChatStreamContent(chatStreamContentRef.current);
    }
  };

  // 获取Agent状态
  const getAgentStatus = (agentKey: string): 'wait' | 'process' | 'finish' => {
    const output = agentOutputs[agentKey];
    if (!output) return 'wait';
    if (output.status === 'running' || activeAgents.has(agentKey)) return 'process';
    return 'finish';
  };

  // 获取当前步骤（返回第一个正在运行的agent的索引）
  const getCurrentStep = (): number => {
    // 找到第一个正在运行的agent
    for (let i = 0; i < AGENTS.length; i++) {
      if (activeAgents.has(AGENTS[i].key)) {
        return i;
      }
    }
    // 如果没有正在运行的，返回最后一个完成的
    for (let i = AGENTS.length - 1; i >= 0; i--) {
      if (agentOutputs[AGENTS[i].key]?.status === 'done') {
        return i;
      }
    }
    return 0;
  };

  // 清空并重新开始
  const resetAll = () => {
    setPaperImages([]);
    setPaperName('');
    setPaperMetadata(null);
    setIsReading(false);
    setIsReadingComplete(false);
    setIsReadingInterrupted(false);
    setActiveAgents(new Set());
    setAgentOutputs({});
    setStreamingContents({});
    streamingContentsRef.current = {};
    setReadingContext({});
    setElapsedTime(null);
    setActivePanel([]);
    setMessages([]);
    setInputValue('');
    setConversationId('');
    pdfFileRef.current = null; // 清空 PDF 文件引用
    // 清除URL参数
    setSearchParams({});
  };

  // 打开历史抽屉
  const openHistoryDrawer = () => {
    loadConversations();
    setHistoryDrawerOpen(true);
  };

  // 选择历史会话
  const selectConversation = (conv: Conversation) => {
    setHistoryDrawerOpen(false);
    resetAll();
    setSearchParams({ conversation_id: conv.id });
    restoreConversation(conv.id);
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部工具栏 */}
      <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid #f0f0f0',
        background: '#fff',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <Space>
          <FileTextOutlined style={{ fontSize: 20, color: '#1890ff' }} />
          <Title level={4} style={{ margin: 0 }}>论文精读助手</Title>
          {paperMetadata && (
            <Tag color="blue">{paperMetadata.title?.slice(0, 30)}...</Tag>
          )}
        </Space>
        <Space>
          <Button
            icon={<HistoryOutlined />}
            onClick={openHistoryDrawer}
          >
            历史记录
          </Button>
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            accept=".pdf"
            onChange={handleFileUpload}
          />
          <Button
            icon={<UploadOutlined />}
            onClick={() => fileInputRef.current?.click()}
            loading={uploading}
          >
            上传PDF
          </Button>
          <Button
            type="primary"
            onClick={startReading}
            loading={isReading}
            disabled={paperImages.length === 0 || isReadingComplete}
          >
            开始精读
          </Button>
          {isReadingInterrupted && (
            <Button
              type="primary"
              danger
              icon={<ReloadOutlined />}
              onClick={continueReading}
              loading={isReading}
              disabled={paperImages.length === 0}
            >
              继续精读
            </Button>
          )}
          <Button onClick={resetAll} icon={<PlusOutlined />}>
            新建
          </Button>
        </Space>
      </div>

      {/* 历史会话抽屉 */}
      <Drawer
        title="历史精读记录"
        placement="left"
        onClose={() => setHistoryDrawerOpen(false)}
        open={historyDrawerOpen}
        width={350}
      >
        {loadingHistory ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin />
          </div>
        ) : conversations.length === 0 ? (
          <Empty description="暂无历史记录" />
        ) : (
          <List
            dataSource={conversations}
            renderItem={(conv) => (
              <List.Item
                style={{ cursor: 'pointer' }}
                onClick={() => selectConversation(conv)}
                actions={[
                  <Button
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteConversation(conv.id);
                    }}
                  />
                ]}
              >
                <List.Item.Meta
                  avatar={<Avatar icon={<FileTextOutlined />} style={{ backgroundColor: '#1890ff' }} />}
                  title={conv.title}
                  description={new Date(conv.updated_at).toLocaleString()}
                />
              </List.Item>
            )}
          />
        )}
      </Drawer>

      {/* 主体区域 - 左右分栏 */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* 左侧对话区域 */}
        <div style={{
          width: '35%',
          minWidth: 300,
          borderRight: '1px solid #f0f0f0',
          display: 'flex',
          flexDirection: 'column',
          background: '#fafafa'
        }}>
          {/* 对话记录 */}
          <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
            {messages.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
                <FileTextOutlined style={{ fontSize: 48, marginBottom: 16 }} />
                <div>上传PDF论文开始精读</div>
              </div>
            ) : (
              <List
                dataSource={messages}
                renderItem={(msg) => (
                  <List.Item style={{
                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    border: 'none',
                    padding: '8px 0'
                  }}>
                    <div style={{
                      maxWidth: '85%',
                      display: 'flex',
                      flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                      alignItems: 'flex-start',
                      gap: 8
                    }}>
                      <Avatar
                        icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                        style={{
                          backgroundColor: msg.role === 'user' ? '#1890ff' :
                            msg.role === 'system' ? '#faad14' : '#52c41a',
                          flexShrink: 0
                        }}
                        size="small"
                      />
                      <div style={{
                        background: msg.role === 'user' ? '#1890ff' :
                          msg.role === 'system' ? '#fff7e6' : '#fff',
                        color: msg.role === 'user' ? '#fff' : '#000',
                        padding: '8px 12px',
                        borderRadius: 8,
                        border: msg.role === 'user' ? 'none' : '1px solid #f0f0f0'
                      }}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                  </List.Item>
                )}
              />
            )}

            {/* 流式问答响应 */}
            {isChatting && chatStreamContent && (
              <div style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8,
                padding: '8px 0'
              }}>
                <Avatar
                  icon={<RobotOutlined />}
                  style={{ backgroundColor: '#52c41a' }}
                  size="small"
                />
                <div style={{
                  background: '#fff',
                  padding: '8px 12px',
                  borderRadius: 8,
                  border: '1px solid #f0f0f0'
                }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {chatStreamContent}
                  </ReactMarkdown>
                  <LoadingOutlined spin style={{ marginLeft: 4, color: '#52c41a' }} />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* 输入区域 */}
          <div style={{
            padding: '12px 16px',
            borderTop: '1px solid #f0f0f0',
            background: '#fff'
          }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <TextArea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onPressEnter={(e) => {
                  if (!e.shiftKey) {
                    e.preventDefault();
                    sendChatMessage();
                  }
                }}
                placeholder={isReadingComplete ? "输入问题，按Enter发送..." : "请先完成论文精读"}
                autoSize={{ minRows: 1, maxRows: 4 }}
                disabled={!isReadingComplete || isChatting}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={sendChatMessage}
                loading={isChatting}
                disabled={!isReadingComplete || !inputValue.trim()}
              />
            </div>
          </div>
        </div>

        {/* 右侧工作空间 */}
        <div
          ref={workspaceRef}
          style={{
            flex: 1,
            overflow: 'auto',
            padding: '16px',
            background: '#f5f5f5'
          }}
        >
          {/* 论文预览 */}
          {paperImages.length > 0 && !isReading && !isReadingComplete && (
            <Card title="论文预览" style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <Image.PreviewGroup>
                  {paperImages.slice(0, 6).map((img, idx) => (
                    <Image
                      key={idx}
                      src={img}
                      width={120}
                      height={160}
                      style={{ objectFit: 'cover', borderRadius: 4 }}
                    />
                  ))}
                </Image.PreviewGroup>
                {paperImages.length > 6 && (
                  <div style={{
                    width: 120,
                    height: 160,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: '#f0f0f0',
                    borderRadius: 4
                  }}>
                    +{paperImages.length - 6}页
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Agent执行进度 */}
          {(isReading || Object.keys(agentOutputs).length > 0) && (
            <Card
              title="精读进度"
              style={{ marginBottom: 16 }}
              extra={elapsedTime && <Text type="secondary">耗时: {elapsedTime.toFixed(1)}s</Text>}
            >
              <Steps
                current={getCurrentStep()}
                size="small"
                items={AGENTS.map((agent) => ({
                  title: agent.name,
                  icon: getAgentStatus(agent.key) === 'process' ? (
                    <LoadingOutlined spin style={{ color: agent.color }} />
                  ) : getAgentStatus(agent.key) === 'finish' ? (
                    <CheckCircleOutlined style={{ color: '#52c41a' }} />
                  ) : (
                    <ClockCircleOutlined style={{ color: '#d9d9d9' }} />
                  ),
                  status: getAgentStatus(agent.key)
                }))}
              />
            </Card>
          )}

          {/* Agent输出详情 */}
          {Object.keys(agentOutputs).length > 0 && (
            <Card title="分析详情">
              <Collapse
                activeKey={activePanel}
                onChange={(keys) => setActivePanel(keys as string[])}
              >
                {AGENTS.map((agent) => {
                  const output = agentOutputs[agent.key];
                  if (!output) return null;

                  return (
                    <Panel
                      key={agent.key}
                      header={
                        <Space>
                          {output.status === 'running' ? (
                            <LoadingOutlined spin style={{ color: agent.color }} />
                          ) : (
                            <CheckCircleOutlined style={{ color: '#52c41a' }} />
                          )}
                          <span style={{ color: agent.color, fontWeight: 500 }}>{agent.name}</span>
                          {output.status === 'running' && <Tag color="processing">执行中</Tag>}
                          {output.status === 'done' && <Tag color="success">完成</Tag>}
                        </Space>
                      }
                    >
                      <div style={{
                        background: '#fafafa',
                        padding: 16,
                        borderRadius: 8,
                        maxHeight: 400,
                        overflow: 'auto'
                      }}>
                        {/* 支持多agent并行显示：每个agent有独立的流式内容 */}
                        {output.status === 'running' && activeAgents.has(agent.key) && streamingContents[agent.key] ? (
                          <div className="markdown-content">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {streamingContents[agent.key]}
                            </ReactMarkdown>
                            <LoadingOutlined spin style={{ marginLeft: 4 }} />
                          </div>
                        ) : output.content ? (
                          <div className="markdown-content">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {output.content}
                            </ReactMarkdown>
                          </div>
                        ) : output.status === 'running' ? (
                          <div>
                            <LoadingOutlined spin style={{ marginRight: 8 }} />
                            <Text type="secondary">正在分析...</Text>
                          </div>
                        ) : (
                          <Text type="secondary">等待输出...</Text>
                        )}
                      </div>
                    </Panel>
                  );
                })}
              </Collapse>
            </Card>
          )}

          {/* 空状态 */}
          {paperImages.length === 0 && (
            <div style={{
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexDirection: 'column',
              color: '#999'
            }}>
              <PictureOutlined style={{ fontSize: 64, marginBottom: 16 }} />
              <Title level={4} style={{ color: '#999' }}>上传PDF论文开始精读</Title>
              <Paragraph type="secondary">
                支持多页论文，AI将自动分析论文结构、方法、创新点
              </Paragraph>
            </div>
          )}
        </div>
      </div>

      {/* 样式 */}
      <style>{`
        .markdown-content h1 { font-size: 1.4em; margin-top: 1em; }
        .markdown-content h2 { font-size: 1.2em; margin-top: 0.8em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
        .markdown-content h3 { font-size: 1.1em; margin-top: 0.6em; }
        .markdown-content ul, .markdown-content ol { padding-left: 20px; }
        .markdown-content li { margin: 4px 0; }
        .markdown-content p { margin: 8px 0; }
        .markdown-content code { background: #f0f0f0; padding: 2px 6px; border-radius: 4px; }
        .markdown-content pre { background: #f0f0f0; padding: 12px; border-radius: 8px; overflow-x: auto; }
        .markdown-content blockquote { border-left: 3px solid #1890ff; padding-left: 12px; color: #666; margin: 8px 0; }
      `}</style>
    </div>
  );
};

export default PaperReaderPage;
