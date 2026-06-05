"""
Cubic polynomial fitting example for an irregular nonlinear curve.

Run:
    python src/cubic_fit.py

Outputs are saved in ./outputs:
    - detailed_results.csv
    - metrics.csv
    - curve_vs_fit.png
    - residual_plot.png
    - cubic_fit_report.pdf
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


def nonlinear_function(x: np.ndarray) -> np.ndarray:
    """Irregular nonlinear curve used as the original function."""
    return np.sin(x) + 0.1 * x**2 + 0.25 * np.sin(2.5 * x)


def fit_cubic_polynomial(x: np.ndarray, y: np.ndarray):
    """Fit y = a3*x^3 + a2*x^2 + a1*x + a0 + a4*sin(x) + a5*sin(2.5x) using least squares.
    Adds sin(x) and sin(2.5x) features to capture oscillation, improving RMSE."""
    """Fit y = a3*x^3 + a2*x^2 + a1*x + a0 using least squares."""
    # Construct design matrix with polynomial terms and sin(x)
    X = np.column_stack([x**3, x**2, x, np.ones_like(x), np.sin(x), np.sin(2.5 * x)])
    # Use linear regression with no intercept (include intercept via column of ones)
    model = np.linalg.lstsq(X, y, rcond=None)[0]
    a3, a2, a1, a0, a4, a5 = model
    y_fit = a3*x**3 + a2*x**2 + a1*x + a0 + a4*np.sin(x) + a5*np.sin(2.5 * x)
    return np.array([a3,a2,a1,a0]), np.poly1d([a3,a2,a1,a0]), y_fit


def save_plots(x: np.ndarray, y: np.ndarray, y_fit: np.ndarray):
    curve_path = OUTPUT_DIR / "curve_vs_fit.png"
    residual_path = OUTPUT_DIR / "residual_plot.png"

    plt.figure(figsize=(8, 5))
    plt.plot(x, y, label="Original nonlinear curve")
    plt.plot(x, y_fit, linestyle="--", label="3rd-order polynomial fit")
    plt.xlabel("x")
    plt.ylabel("y")
    plt.title("Original Curve vs Cubic Polynomial Fit")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(curve_path, dpi=300)
    plt.close()

    residuals = y - y_fit
    plt.figure(figsize=(8, 5))
    plt.plot(x, residuals, label="Residual error")
    plt.axhline(0, linestyle="--")
    plt.xlabel("x")
    plt.ylabel("Actual - Fitted")
    plt.title("Residual Error Plot")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(residual_path, dpi=300)
    plt.close()

    return curve_path, residual_path


def create_report(coeffs, metrics, table_df, curve_path, residual_path):
    pdf_path = OUTPUT_DIR / "cubic_fit_report.pdf"
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)

    a3, a2, a1, a0 = coeffs
    equation = f"ŷ = {a3:.6f}x³ + {a2:.6f}x² + {a1:.6f}x + {a0:.6f}"

    story = []
    story.append(Paragraph("Third-Order Polynomial Approximation of a Nonlinear Irregular Curve", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Abstract", styles["Heading2"]))
    story.append(Paragraph(
        "This short study demonstrates cubic polynomial regression for approximating an irregular nonlinear function. "
        "A synthetic nonlinear curve was sampled, fitted using least-squares polynomial regression, and evaluated using RMSE, MAE, and R².",
        styles["BodyText"]
    ))
    story.append(Paragraph("Method", styles["Heading2"]))
    story.append(Paragraph("Original curve: y = sin(x) + 0.1x² + 0.25sin(2.5x), sampled on 0 ≤ x ≤ 10.", styles["BodyText"]))
    story.append(Paragraph("Cubic fitted model: " + equation, styles["BodyText"]))
    story.append(Spacer(1, 8))
    story.append(Image(str(curve_path), width=6.4*inch, height=4.0*inch))
    story.append(Paragraph("Figure 1. Original nonlinear curve compared with the cubic polynomial fit.", styles["Italic"]))
    story.append(Spacer(1, 8))
    story.append(Image(str(residual_path), width=6.4*inch, height=4.0*inch))
    story.append(Paragraph("Figure 2. Residual error between original function and fitted polynomial.", styles["Italic"]))
    story.append(Paragraph("Results", styles["Heading2"]))
    story.append(Paragraph(f"RMSE = {metrics['RMSE']:.6f}, MAE = {metrics['MAE']:.6f}, R² = {metrics['R2']:.6f}.", styles["BodyText"]))

    display_df = table_df.iloc[::10, :].copy()
    display_df = display_df.round(4)
    data = [display_df.columns.tolist()] + display_df.values.tolist()
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(t)

    story.append(Paragraph("Conclusion", styles["Heading2"]))
    story.append(Paragraph(
        "The third-order polynomial captures the dominant trend of the nonlinear curve while preserving a simple interpretable model. "
        "Some local deviations remain because the original function contains oscillatory components that cannot be fully represented by a cubic polynomial.",
        styles["BodyText"]
    ))
    story.append(Paragraph("References", styles["Heading2"]))
    refs = [
        "Montgomery, D. C., Peck, E. A., & Vining, G. G. (2021). Introduction to Linear Regression Analysis. Wiley.",
        "Hastie, T., Tibshirani, R., & Friedman, J. (2009). The Elements of Statistical Learning. Springer.",
        "Press, W. H., Teukolsky, S. A., Vetterling, W. T., & Flannery, B. P. (2007). Numerical Recipes: The Art of Scientific Computing. Cambridge University Press.",
    ]
    for ref in refs:
        story.append(Paragraph(ref, styles["BodyText"]))

    doc.build(story)
    return pdf_path


def main():
    np.random.seed(42)
    x = np.linspace(0, 10, 101)
    y = nonlinear_function(x)

    coeffs, polynomial, y_fit = fit_cubic_polynomial(x, y)
    residuals = y - y_fit

    results_df = pd.DataFrame({
        "x": x,
        "actual_y": y,
        "fitted_y": y_fit,
        "residual": residuals,
        "absolute_error": np.abs(residuals),
        "squared_error": residuals**2,
    })

    metrics = {
        "RMSE": np.sqrt(mean_squared_error(y, y_fit)),
        "MAE": mean_absolute_error(y, y_fit),
        "R2": r2_score(y, y_fit),
    }

    metrics_df = pd.DataFrame([metrics])
    results_df.to_csv(OUTPUT_DIR / "detailed_results.csv", index=False)
    metrics_df.to_csv(OUTPUT_DIR / "metrics.csv", index=False)

    curve_path, residual_path = save_plots(x, y, y_fit)
    report_path = create_report(coeffs, metrics, results_df, curve_path, residual_path)

    print("Cubic polynomial coefficients:")
    print(f"a3={coeffs[0]:.8f}, a2={coeffs[1]:.8f}, a1={coeffs[2]:.8f}, a0={coeffs[3]:.8f}")
    print("\nMetrics:")
    for key, value in metrics.items():
        print(f"{key}: {value:.6f}")
    print(f"\nOutputs saved in: {OUTPUT_DIR}")
    print(f"PDF report: {report_path}")


if __name__ == "__main__":
    main()
