/**
 * 登录页面
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Form, Input, Button, Tabs, message, Typography, Space, Divider } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined, LoginOutlined } from '@ant-design/icons';
import { login, register, guestLogin } from '../../services/auth-service';
import { useUser } from '../../contexts/UserContext';

const { Title, Text } = Typography;

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { setUser } = useUser();
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('login');

  // 登录表单
  const handleLogin = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const result = await login(values.username, values.password);
      if (result.success && result.data) {
        const { token, ...user } = result.data;
        setUser(user);
        message.success('登录成功');
        navigate('/paper-reader');
      } else {
        message.error(result.msg || '登录失败');
      }
    } catch (error: any) {
      message.error(error.response?.data?.msg || '登录失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 注册表单
  const handleRegister = async (values: {
    username: string;
    password: string;
    confirmPassword: string;
    email?: string;
    nickname?: string;
  }) => {
    if (values.password !== values.confirmPassword) {
      message.error('两次输入的密码不一致');
      return;
    }

    setLoading(true);
    try {
      const result = await register(
        values.username,
        values.password,
        values.email,
        values.nickname
      );
      if (result.success && result.data) {
        const { token, ...user } = result.data;
        setUser(user);
        message.success('注册成功');
        navigate('/paper-reader');
      } else {
        message.error(result.msg || '注册失败');
      }
    } catch (error: any) {
      message.error(error.response?.data?.msg || '注册失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 游客登录
  const handleGuestLogin = async () => {
    setLoading(true);
    try {
      const result = await guestLogin();
      if (result.success && result.data) {
        const { token, ...user } = result.data;
        setUser(user);
        message.success('游客登录成功');
        navigate('/paper-reader');
      } else {
        message.error(result.msg || '游客登录失败');
      }
    } catch (error: any) {
      message.error(error.response?.data?.msg || '游客登录失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  const tabItems = [
    {
      key: 'login',
      label: '登录',
      children: (
        <Form
          name="login"
          onFinish={handleLogin}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名或邮箱' }]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名或邮箱"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
            />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
            >
              登录
            </Button>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'register',
      label: '注册',
      children: (
        <Form
          name="register"
          onFinish={handleRegister}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, max: 32, message: '用户名长度需在3-32个字符之间' },
            ]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名"
            />
          </Form.Item>

          <Form.Item
            name="email"
          >
            <Input
              prefix={<MailOutlined />}
              placeholder="邮箱（可选）"
            />
          </Form.Item>

          <Form.Item
            name="nickname"
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="昵称（可选）"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码长度至少6个字符' },
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
            />
          </Form.Item>

          <Form.Item
            name="confirmPassword"
            rules={[
              { required: true, message: '请确认密码' },
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="确认密码"
            />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
            >
              注册
            </Button>
          </Form.Item>
        </Form>
      ),
    },
  ];

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        padding: '20px',
      }}
    >
      <Card
        style={{
          width: '100%',
          maxWidth: 420,
          borderRadius: 12,
          boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
        }}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div style={{ textAlign: 'center' }}>
            <Title level={2} style={{ margin: 0, color: '#1890ff' }}>
              Hajimi Paper Reader
            </Title>
            <Text type="secondary">论文精读工作台</Text>
          </div>

          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={tabItems}
            centered
          />

          <Divider plain>
            <Text type="secondary">或</Text>
          </Divider>

          <Button
            icon={<LoginOutlined />}
            onClick={handleGuestLogin}
            loading={loading}
            block
            size="large"
          >
            游客体验
          </Button>

          <Text
            type="secondary"
            style={{ display: 'block', textAlign: 'center', fontSize: 12 }}
          >
            游客数据将在7天后自动清理
          </Text>
        </Space>
      </Card>
    </div>
  );
};

export default LoginPage;
