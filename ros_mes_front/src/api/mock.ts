//现在没有后端，我就延迟 300ms，模拟一个后端成功返回。
import type { ApiResponse } from "./types";

export const useMock = import.meta.env.VITE_USE_MOCK === "true";

export function mockSuccess<T>(data: T, message = "操作成功"): Promise<ApiResponse<T>> {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        code: 200,
        message,
        data,
      });
    }, 300);
  });
}