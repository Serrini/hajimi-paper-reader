import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { UserProvider, useUser } from './contexts/UserContext';
import PaperReaderPage from './pages/paper-reader';
import LoginPage from './pages/login';
import Layout from './components/layout';

// 路由保护组件
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useUser();

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>加载中...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

// 登录页面路由保护（已登录用户跳转到首页）
const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useUser();

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>加载中...</div>;
  }

  if (isAuthenticated) {
    return <Navigate to="/paper-reader" replace />;
  }

  return <>{children}</>;
};

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* 公开路由 */}
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />

      {/* 受保护的路由 */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout>
              <Navigate to="/paper-reader" replace />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/paper-reader"
        element={
          <ProtectedRoute>
            <Layout>
              <PaperReaderPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/paper-reader" replace />} />
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <ConfigProvider
      theme={{
        token: {
          fontFamily: 'Inter',
        },
        algorithm: theme.defaultAlgorithm,
      }}
      locale={zhCN}
    >
      <UserProvider>
        <Router>
          <AppRoutes />
        </Router>
      </UserProvider>
    </ConfigProvider>
  );
};

export default App;
