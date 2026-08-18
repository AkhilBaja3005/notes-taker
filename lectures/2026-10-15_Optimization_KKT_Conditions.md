---
date: 2026-10-15
course: "[[Optimization]]"
topic: "[[KKT Conditions]]"
source_file: "Optimization_KKT-Conditions_2026-10-15.m4a"
model_used: "gemini-3.6-flash"
tags:
  - course/Optimization
  - topic/KKTConditions
  - graduate-notes
---

# Optimization: KKT Conditions

## 1. Executive Summary
- **Convex Optimization Framework**: The Karush-Kuhn-Tucker (KKT) conditions extend Lagrange multipliers to optimization problems involving inequality constraints $g_i(x) \le 0$.
- **Necessary & Sufficient Conditions**: For convex, differentiable optimization problems, satisfying the KKT conditions provides necessary and sufficient guarantees for global optimality.
- **Core Triad + Stationarity**: Global optimality requires primal feasibility ($g_i(x) \le 0$), dual feasibility ($\lambda_i \ge 0$), stationarity ($\nabla L = 0$), and complementary slackness ($\lambda_i g_i(x) = 0$).
- **Midterm Priority**: Proving strong duality under Slater's constraint qualification condition is explicitly identified as an upcoming exam requirement.

---

## 2. Mathematical Definitions, Derivations & Proofs

### Convex Optimization Problem Setup
Let $f: \mathbb{R}^n \to \mathbb{R}$ and $g_i: \mathbb{R}^n \to \mathbb{R}$ ($i = 1, \dots, m$) be continuously differentiable, convex functions.

$$\begin{aligned}
\min_{x \in \mathbb{R}^n} \quad & f(x) \\
\text{subject to} \quad & g_i(x) \le 0, \quad i = 1, \dots, m
\end{aligned}$$

### Lagrangian Formulation
The Lagrangian function $L: \mathbb{R}^n \times \mathbb{R}^m \to \mathbb{R}$ combines the objective function and weighted constraints:
$$L(x, \lambda) = f(x) + \sum_{i=1}^m \lambda_i g_i(x)$$

where $\lambda = (\lambda_1, \dots, \lambda_m)^T$ is the vector of Lagrange multipliers (dual variables).

---

### Karush-Kuhn-Tucker (KKT) Conditions
A point $x^*$ and dual vector $\lambda^*$ form an optimal primal-dual pair $(x^*, \lambda^*)$ if and only if they satisfy:

1. **Primal Feasibility**:
   $$g_i(x^*) \le 0, \quad \forall i \in \{1, \dots, m\}$$

2. **Dual Feasibility**:
   $$\lambda_i^* \ge 0, \quad \forall i \in \{1, \dots, m\}$$

3. **Complementary Slackness**:
   $$\lambda_i^* g_i(x^*) = 0, \quad \forall i \in \{1, \dots, m\}$$

4. **Stationarity**:
   $$\nabla_x L(x^*, \lambda^*) = \nabla f(x^*) + \sum_{i=1}^m \lambda_i^* \nabla g_i(x^*) = 0$$

---

### Strong Duality & Slater's Condition
Let $p^*$ be the optimal value of the primal problem and $d^*$ be the optimal value of the dual problem.

- **Weak Duality**: $d^* \le p^*$ always holds.
- **Strong Duality**: $p^* = d^*$ (zero duality gap).

#### Slater's Condition (Constraint Qualification)
Strong duality holds for a convex problem if there exists a strictly feasible point $x_0 \in \mathbf{relint}(\mathcal{D})$ such that:
$$g_i(x_0) < 0, \quad \forall i = 1, \dots, m$$

Under Slater's condition, there exists a dual optimal point $\lambda^* \ge 0$ satisfying the KKT conditions at $x^*$.

---

## 3. High-Yield Exam Notes & Professor Emphasis

> [!WARNING] Exam Pitfalls & Professor Warnings
> - **Explicit Midterm Exam Topic**: You will be required to write a formal proof of **strong duality under Slater's condition** on the midterm examination.
> - **Multiplier Sign Conventions**: Inequality constraints expressed as $g_i(x) \le 0$ dictate $\lambda_i \ge 0$. If written as $g_i(x) \ge 0$, the corresponding multiplier sign flips.
> - **Complementary Slackness Application**: $\lambda_i^* g_i(x^*) = 0$ implies a strict trade-off:
>   - If constraint $i$ is inactive ($g_i(x^*) < 0$), then $\lambda_i^* = 0$.
>   - If $\lambda_i^* > 0$, the constraint must be active ($g_i(x^*) = 0$).

---

## 4. Key Concept Q&A Flashcards

**Q1: What are the four KKT conditions for a standard convex inequality-constrained problem?**
> **A1:** Primal feasibility ($g_i(x) \le 0$), Dual feasibility ($\lambda_i \ge 0$), Complementary slackness ($\lambda_i g_i(x) = 0$), and Stationarity ($\nabla f(x) + \sum \lambda_i \nabla g_i(x) = 0$).

**Q2: Under what conditions are the KKT conditions both necessary and sufficient for global optimality?**
> **A2:** When the objective function $f(x)$ and inequality constraint functions $g_i(x)$ are convex and continuously differentiable, and a constraint qualification (such as Slater's condition) holds.

**Q3: What does Slater's condition require?**
> **A3:** It requires the existence of at least one point $x_0$ in the relative interior of the domain that strictly satisfies all inequality constraints ($g_i(x_0) < 0$ for all $i$).

**Q4: What is the mechanical meaning of complementary slackness ($\lambda_i g_i(x) = 0$)?**
> **A4:** It means that inactive constraints ($g_i(x) < 0$) have zero impact on the dual objective ($\lambda_i = 0$), whereas active constraints ($g_i(x) = 0$) can have positive dual multipliers ($\lambda_i \ge 0$).

**Q5: What is the duality gap under strong duality?**
> **A5:** The duality gap is zero ($p^* - d^* = 0$), meaning the optimal primal objective value equals the optimal dual objective value.

---

## 5. Chronological / Sectional Breakdown

| Timestamp | Topic / Section | Core Concept Summary |
| :--- | :--- | :--- |
| **[00:00:00]** | Introduction & Context | Welcome to Graduate Optimization Theory; introduction of Karush-Kuhn-Tucker (KKT) optimality conditions for convex problems. |
| **[00:00:08]** | Problem Formulation | Definition of convex objective function $f(x)$ and inequality constraints $g_i(x) \le 0$. |
| **[00:00:15]** | Core KKT Conditions | Statement of necessary and sufficient conditions for global optimality: primal feasibility, dual feasibility, and complementary slackness ($\lambda_i \cdot g_i(x) = 0$). |
| **[00:00:26]** | Professor Midterm Warning | Direct alert: Proving strong duality under Slater's condition will be tested on the midterm examination. |
