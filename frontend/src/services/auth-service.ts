/**
 * 用户认证服务
 */
import axios from 'axios';
import API_BASE_URL from '../config';

const API_BASE = API_BASE_URL;

// Token 存储 key
const TOKEN_KEY = 'imem_token';
const USER_KEY = 'imem_user';

export interface User {
  user_id: string;
  username: string;
  nickname: string;
  email?: string;
  avatar?: string;
  is_guest: boolean;
}

export interface LoginResponse {
  success: boolean;
  msg: string;
  data?: User & { token: string };
}

// 创建带认证的 axios 实例
export const authAxios = axios.create({
  baseURL: API_BASE,
  timeout: 120000, // 120秒超时，Agent 响应可能较慢
});

// 请求拦截器：添加 token
authAxios.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：处理 401 错误
authAxios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token 过期或无效，清除本地存储
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

/**
 * 用户注册
 */
export const register = async (
  username: string,
  password: string,
  email?: string,
  nickname?: string
): Promise<LoginResponse> => {
  const response = await axios.post(`${API_BASE}/auth/register`, {
    username,
    password,
    email,
    nickname,
  });

  if (response.data.success && response.data.data) {
    const { token, ...user } = response.data.data;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  return response.data;
};

/**
 * 用户登录
 */
export const login = async (
  username: string,
  password: string
): Promise<LoginResponse> => {
  const response = await axios.post(`${API_BASE}/auth/login`, {
    username,
    password,
  });

  if (response.data.success && response.data.data) {
    const { token, ...user } = response.data.data;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  return response.data;
};

/**
 * 游客登录
 */
export const guestLogin = async (): Promise<LoginResponse> => {
  const response = await axios.post(`${API_BASE}/auth/guest`);

  if (response.data.success && response.data.data) {
    const { token, ...user } = response.data.data;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  return response.data;
};

/**
 * 退出登录
 */
export const logout = (): void => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};

/**
 * 获取当前用户
 */
export const getCurrentUser = (): User | null => {
  const userStr = localStorage.getItem(USER_KEY);
  if (userStr) {
    try {
      return JSON.parse(userStr);
    } catch {
      return null;
    }
  }
  return null;
};

/**
 * 获取 Token
 */
export const getToken = (): string | null => {
  return localStorage.getItem(TOKEN_KEY);
};

/**
 * 是否已登录
 */
export const isLoggedIn = (): boolean => {
  return !!getToken();
};

/**
 * 获取用户信息
 */
export const getUserInfo = async (): Promise<User | null> => {
  try {
    const response = await authAxios.get('/auth/me');
    if (response.data.success) {
      localStorage.setItem(USER_KEY, JSON.stringify(response.data.data));
      return response.data.data;
    }
    return null;
  } catch {
    return null;
  }
};

export default {
  register,
  login,
  guestLogin,
  logout,
  getCurrentUser,
  getToken,
  isLoggedIn,
  getUserInfo,
};
