import React from 'react';
import { RouteObject } from 'react-router-dom';

// 页面组件导入
const PaperReaderPage = React.lazy(() => import('./pages/paper-reader'));

// 路由配置
export const routes: RouteObject[] = [
  {
    path: '/',
    element: React.createElement(PaperReaderPage)
  },
  {
    path: '/paper-reader',
    element: React.createElement(PaperReaderPage)
  }
];

export default routes;
