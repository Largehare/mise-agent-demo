import numpy as np

def jenkins_traub_no_shift_demo(P_coeffs, iterations=5):
    """
    Jenkins-Traub 算法 Stage 1 (无位移阶段) 概念演示
    
    参数:
    P_coeffs: 多项式 P(z) 的系数，按升幂排列 [a_0, a_1, ..., a_n]
              即 P(z) = a_0 + a_1*z + a_2*z^2 + ... + a_n*z^n
    iterations: 迭代次数
    """
    P = np.array(P_coeffs, dtype=float)
    n = len(P) - 1
    
    # 初始化 H0(z) 为 P(z) 的导数 P'(z)
    # P'(z) = a_1 + 2*a_2*z + ... + n*a_n*z^{n-1}
    H = np.array([P[i] * i for i in range(1, n + 1)], dtype=float)
    
    print(f"原多项式 P(z) 系数 (升幂): {P}")
    print(f"初始 H0(z) 系数 (升幂): {H}\n")
    
    # 开始无位移迭代
    for k in range(iterations):
        # 核心公式: H_{k+1}(z) = ( H_k(z) - (H_k(0)/P(0)) * P(z) ) / z
        
        # 1. 计算常数项比例 alpha = H_k(0) / P(0)
        # 在升幂排列中，索引 0 就是常数项
        alpha = H[0] / P[0] 
        
        # 2. 构造 H_k(z) - alpha * P(z)
        # 因为 P 是 n 次，H 是 n-1 次，需要给 H 补齐一个最高次项(0)以便于数组相减
        H_padded = np.pad(H, (0, 1), mode='constant', constant_values=0)
        temp_poly = H_padded - alpha * P
        
        # 数学上，此时 temp_poly 的常数项 (temp_poly[0]) 必定为 0
        # 3. 除以 z，即把所有系数的幂次降 1 (在数组中就是去掉索引 0 的项)
        H_next = temp_poly[1:]
        
        H = H_next
        print(f"Iteration {k+1}: H_{k+1}(z) = {np.round(H, 4)}")
        
    return H

# --- 测试用例 ---
# 构造一个多项式 P(z) = (z-1)(z-2)(z-3) = -6 + 11z - 6z^2 + z^3
# 根为 1, 2, 3。其中最小的根是 1。
# 升幂排列系数 [a_0, a_1, a_2, a_3]
P_test = [-6, 11, -6, 1]

print("--- Jenkins-Traub 无位移 H多项式迭代演示 ---")
final_H = jenkins_traub_no_shift_demo(P_test, iterations=8)

# 验证 H 多项式的根
# H 多项式的根应该逐渐逼近去除了最小根(1)之后的根，即逼近 2 和 3。
H_roots = np.roots(final_H[::-1]) # np.roots 需要降幂排列的系数
print(f"\n迭代后 H 多项式的根为: {np.round(H_roots, 4)}")
print("可以看到，H 多项式的根越来越逼近 2 和 3，从而在后续阶段能轻易分离出最小根 1。")