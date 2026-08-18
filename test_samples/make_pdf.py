from pypdf import PdfWriter
import io
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(8.5, 11))
ax.axis('off')

content = """
GRADUATE MACHINE LEARNING (CS 701)
Lecture Notes: Backpropagation and Computational Graphs
Date: 2026-10-15
Instructor: Prof. Turing

1. Executive Overview:
Backpropagation is an efficient application of the multivariable chain rule
over directed acyclic computational graphs (DAG).

2. Mathematical Formulation:
Let L be the scalar loss, and W^(l) be the weight matrix at layer l.
The forward pass is defined as:
    Z^(l) = W^(l) * A^(l-1) + b^(l)
    A^(l) = sigma(Z^(l))

By the chain rule, the error term delta^(l) is:
    delta^(l) = dL / dZ^(l) = (W^(l+1))^T * delta^(l+1) odot sigma'(Z^(l))

The weight gradient is given by:
    dL / dW^(l) = delta^(l) * (A^(l-1))^T

3. High-Yield Exam Notes:
- Sliders and matrix dimension checks are guaranteed exam questions.
- Always check that dL / dW^(l) matches the exact dimension of W^(l).
- Vanishing gradient occurs when sigma'(Z) approaches 0 for saturated activations like Sigmoid.

4. Practice Check:
Q: Why do we cache intermediate activations A^(l-1) during the forward pass?
A: Because they are explicitly required to compute the weight gradient dL/dW during backprop.
"""

plt.text(0.05, 0.95, content, fontsize=11, fontfamily='monospace', va='top')
buf = io.BytesIO()
plt.savefig("test_samples/Machine-Learning_Backpropagation_2026-10-15.pdf", format='pdf', bbox_inches='tight')
plt.close(fig)
print("[+] PDF Generated successfully")
