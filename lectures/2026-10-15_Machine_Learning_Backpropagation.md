---
date: 2026-10-15
course: "[[Machine Learning]]"
topic: "[[Backpropagation]]"
source_file: "Machine-Learning_Backpropagation_2026-10-15.pdf"
model_used: "gemini-3.6-flash"
tags:
  - course/MachineLearning
  - topic/Backpropagation
  - graduate-notes
---

# Machine Learning: Backpropagation

## 1. Executive Summary
- **Algorithmic Basis**: Backpropagation is an efficient linear-time application of the multivariable chain rule over computational topologies represented as Directed Acyclic Graphs (DAGs).
- **Forward vs. Backward Pass**: The forward pass computes pre-activations $Z^{(l)}$ and non-linear activations $A^{(l)}$ sequentially, caching intermediate states required to compute parameter updates during the backward pass.
- **Error Propagation**: The error signal vector $\delta^{(l)}$ is recursively propagated backward from layer $l+1$ to layer $l$ via transposition of the weight matrix and element-wise scaling by activation derivatives.
- **Gradient Construction**: Weight gradients $\frac{\partial L}{\partial W^{(l)}}$ are expressed directly as the outer product of the current layer's error vector $\delta^{(l)}$ and the transposed activation vector from the preceding layer $(A^{(l-1)})^T$.
- **Pathological Dynamics**: Saturating activation functions (e.g., Sigmoid) drive derivative terms $\sigma'(Z^{(l)}) \to 0$, inducing the vanishing gradient problem in deep architectures.

---

## 2. Mathematical Definitions, Derivation & Equations

### State Variables & Dimensionality
Let the network at layer $l \in \{1, \dots, L\}$ be defined with the following variables:
* $L \in \mathbb{R}$: Scalar loss objective function.
* $W^{(l)} \in \mathbb{R}^{n_l \times n_{l-1}}$: Weight matrix for layer $l$.
* $b^{(l)} \in \mathbb{R}^{n_l}$: Bias vector for layer $l$.
* $Z^{(l)} \in \mathbb{R}^{n_l}$: Linear combination / pre-activation vector at layer $l$.
* $A^{(l)} \in \mathbb{R}^{n_l}$: Post-activation output vector at layer $l$ (where $A^{(0)} = X$, the input data).
* $\sigma(\cdot)$: Pointwise non-linear activation function.
* $\odot$: Hadamard (element-wise) matrix product.
* $\delta^{(l)} \equiv \frac{\partial L}{\partial Z^{(l)}} \in \mathbb{R}^{n_l}$: Layer error vector.

---

### Forward Pass Equations
For layer $l$:
$$Z^{(l)} = W^{(l)} A^{(l-1)} + b^{(l)}$$
$$A^{(l)} = \sigma\left(Z^{(l)}\right)$$

---

### Backward Pass & Gradient Equations

#### 1. Layer Error Propagation Term ($\delta^{(l)}$)
By applying the vector-valued multivariable chain rule across computational steps $Z^{(l)} \to A^{(l)} \to Z^{(l+1)} \to L$:

$$\delta^{(l)} = \frac{\partial L}{\partial Z^{(l)}} = \left(W^{(l+1)}\right)^T \delta^{(l+1)} \odot \sigma'\left(Z^{(l)}\right)$$

#### 2. Weight Parameter Gradient ($\frac{\partial L}{\partial W^{(l)}}$)
Applying the derivative with respect to the matrix parameters $W^{(l)}$:

$$\frac{\partial L}{\partial W^{(l)}} = \delta^{(l)} \left(A^{(l-1)}\right)^T$$

*Dimension Verification Check*:
* $\delta^{(l)} \in \mathbb{R}^{n_l \times 1}$
* $(A^{(l-1)})^T \in \mathbb{R}^{1 \times n_{l-1}}$
* $\frac{\partial L}{\partial W^{(l)}} \in \mathbb{R}^{n_l \times n_{l-1}} = \operatorname{dim}\left(W^{(l)}\right)$ $\quad \checkmark$

---

## 3. High-Yield Exam Notes & Professor Emphasis

> [!WARNING] Exam Pitfalls & Professor Warnings
> - **Matrix Dimension Verification**: Dimension checks on parameter gradients are guaranteed exam questions. Always explicitly verify that $\operatorname{dim}\left(\frac{\partial L}{\partial W^{(l)}}\right) = \operatorname{dim}\left(W^{(l)}\right) = (n_l \times n_{l-1})$.
> - **Outer Product Order**: A common mistake is swapping the order in the weight gradient formula. Remember: $\frac{\partial L}{\partial W^{(l)}} = \delta^{(l)} (A^{(l-1)})^T$, NOT $A^{(l-1)} (\delta^{(l)})^T$.
> - **Vanishing Gradient Pathology**: Occurs when pre-activations $Z^{(l)}$ enter the saturated regime of activation functions like Sigmoid ($\sigma'(Z^{(l)}) \approx 0$). Multiplying by near-zero terms recursively drives $\delta^{(l)} \to 0$ for early layers.
> - **Memory Caching Necessity**: Intermediate activations $A^{(l-1)}$ MUST be stored in RAM during the forward pass; without caching, computing $\frac{\partial L}{\partial W^{(l)}}$ requires redundant re-computation of the forward pass.

---

## 4. Key Concept Q&A Flashcards

**Q1: What underlying graph representation is assumed when executing backpropagation?**  
**A1:** Directed Acyclic Graphs (DAGs), over which multivariable chain rule operations can be evaluated deterministically.

**Q2: What is the formal definition of the error vector $\delta^{(l)}$ at layer $l$?**  
**A2:** $\delta^{(l)}$ is defined as the partial derivative of the scalar loss $L$ with respect to the pre-activation vector $Z^{(l)}$, i.e., $\delta^{(l)} = \frac{\partial L}{\partial Z^{(l)}}$.

**Q3: Why are intermediate activations $A^{(l-1)}$ cached during the forward pass?**  
**A3:** Because the weight gradient update $\frac{\partial L}{\partial W^{(l)}} = \delta^{(l)} (A^{(l-1)})^T$ explicitly depends on the activation outputs from the preceding layer.

**Q4: How does the Hadamard product ($\odot$) function in the error term formula?**  
**A4:** It performs element-wise multiplication between the backpropagated error vector $(W^{(l+1)})^T \delta^{(l+1)}$ and the element-wise derivative of the activation function evaluated at $Z^{(l)}$.

**Q5: What mathematical condition causes the vanishing gradient problem in networks with Sigmoid activations?**  
**A5:** When $|Z^{(l)}|$ becomes large, the activation function saturates, causing its derivative $\sigma'(Z^{(l)}) \to 0$. Since $\delta^{(l)}$ scales directly with $\sigma'(Z^{(l)})$, early layers receive near-zero updates.

**Q6: What is the shape of the gradient matrix $\frac{\partial L}{\partial W^{(l)}}$ for a layer with $n_{l-1}$ inputs and $n_l$ output neurons?**  
**A6:** It has dimensions $(n_l \times n_{l-1})$, matching the shape of the weight matrix $W^{(l)}$.

---

## 5. Chronological / Sectional Breakdown

### Section 1: Executive Overview
* **Focus**: Fundamental definition of backpropagation.
* **Key Concept**: Backpropagation as an algorithmic realization of the multivariable chain rule on directed acyclic computational graphs.

### Section 2: Mathematical Formulation
* **Focus**: Formal matrix/vector definitions for feedforward propagation and error backpropagation.
* **Key Formulas**:
  * Forward activation steps: $Z^{(l)} = W^{(l)} A^{(l-1)} + b^{(l)}$ and $A^{(l)} = \sigma(Z^{(l)})$.
  * Error update rule: $\delta^{(l)} = (W^{(l+1)})^T \delta^{(l+1)} \odot \sigma'(Z^{(l)})$.
  * Weight gradient update rule: $\frac{\partial L}{\partial W^{(l)}} = \delta^{(l)} (A^{(l-1)})^T$.

### Section 3: High-Yield Exam Notes
* **Focus**: Core exam test points and common implementation errors.
* **Key Takeaways**:
  * Mandatory dimensional matching checks for gradient matrices vs. parameter matrices.
  * Theoretical underpinnings of the vanishing gradient phenomenon due to $\sigma'(Z) \approx 0$.

### Section 4: Practice Check
* **Focus**: Applied conceptual validation.
* **Key Takeaway**: Explanation of memory trade-offs ( caching $A^{(l-1)}$ in forward pass) to enable linear time computation during backward pass.
