import React, { useState } from 'react';
import { Layout, Menu, Space, Avatar, Dropdown, Typography, Tag } from 'antd';
import {
  UserOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ReadOutlined
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

interface LayoutProps {
  children: React.ReactNode;
}

const AppLayout: React.FC<LayoutProps> = ({ children }: LayoutProps) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useUser();
  const [collapsed, setCollapsed] = useState(false);

  const menuItems = [
    {
      key: '/paper-reader',
      icon: <ReadOutlined />,
      label: '论文精读',
    },
  ];

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // 用户下拉菜单
  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  // 确保当前路径在菜单中
  const currentPath = location.pathname === '/' ? '/paper-reader' : location.pathname;

  return (
    <Layout style={{ height: '100vh' }}>
      <Header style={{
        background: '#fff',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid #f0f0f0'
      }}>
        <Space>
          <div
            onClick={() => setCollapsed(!collapsed)}
            style={{
              fontSize: '18px',
              cursor: 'pointer',
              padding: '0 8px',
              display: 'flex',
              alignItems: 'center'
            }}
          >
            {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </div>
          <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#1890ff' }}>
            Hajimi Paper Reader
          </div>
        </Space>
        <Space size="middle">
          {user && (
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Space style={{ cursor: 'pointer' }}>
                <Avatar
                  size="small"
                  icon={<UserOutlined />}
                  src={user.avatar}
                  style={{ backgroundColor: user.is_guest ? '#87d068' : '#1890ff' }}
                />
                <Text>{user.nickname || user.username}</Text>
                {user.is_guest && (
                  <Tag color="green" style={{ marginLeft: 4 }}>游客</Tag>
                )}
              </Space>
            </Dropdown>
          )}
        </Space>
      </Header>
      <Layout>
        <Sider
          width={200}
          collapsedWidth={60}
          collapsed={collapsed}
          style={{
            background: '#fff',
            transition: 'all 0.2s'
          }}
        >
          <Menu
            mode="inline"
            selectedKeys={[currentPath]}
            style={{ height: '100%', borderRight: 0 }}
            items={menuItems}
            onClick={handleMenuClick}
          />
        </Sider>
        <Layout style={{ padding: '0' }}>
          <Content style={{
            margin: 0,
            minHeight: 280,
            background: '#f5f5f5',
            overflow: 'auto'
          }}>
            {children}
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
