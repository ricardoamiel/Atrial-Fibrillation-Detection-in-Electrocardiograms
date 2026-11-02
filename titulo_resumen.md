# Propuesta de proyecto: título y resumen

## Título

Detección de fibrilación auricular en electrocardiogramas de cuidados intensivos: reproducción de referencias con clasificadores basados en características y ampliación explicable mediante transformadas wavelet y de Radón

## Resumen en español

La fibrilación auricular es la arritmia más frecuente en la unidad de cuidados intensivos (UCI) y su detección automática resulta difícil por el ruido, el movimiento del paciente y el número reducido de derivaciones de los monitores de cabecera. Este trabajo reproduce los resultados de Nassar et al. (Abolmaesumi y Mousavi, 2025), que publicaron un conjunto de 596 electrocardiogramas de UCI de cuatro derivaciones y compararon clasificadores basados en características, redes convolucionales y modelos fundacionales. La reproducción se centra en los clasificadores basados en características. Las señales del conjunto público de la competencia PhysioNet/CinC 2021 se filtran con un filtro Butterworth pasabanda de 5 a 30 Hz aplicado en ambos sentidos y se remuestrean a 240 Hz. Luego se detectan los picos R y se calculan 27 rasgos por derivación, entre ellos rasgos de variabilidad de la frecuencia cardiaca en el tiempo, del diagrama de Poincaré y de entropía. Con estos rasgos se entrenan los mismos modelos del artículo: k vecinos más cercanos, perceptrón multicapa, máquina de vectores de soporte, regresión logística, bosque aleatorio, LightGBM, XGBoost y CatBoost. El desempeño se mide con AUROC, AUPRC, F1, especificidad, exactitud balanceada y coeficiente de Matthews. El análisis se amplía con herramientas vistas en el curso. La transformada wavelet discreta da energías y entropías por subbanda del electrocardiograma y de la serie de intervalos RR. El escalograma de la transformada wavelet continua muestra la actividad auricular. La transformada de Radón se aplica a los diagramas de recurrencia y a los escalogramas para obtener rasgos de orientación que separan el ritmo regular del irregular. El análisis espectral de Fourier estima la frecuencia dominante de las ondas fibrilatorias, y el límite inferior de Cramér Rao acota la varianza de la frecuencia cardiaca estimada en ventanas de 10 s. Por último, los valores SHAP explican qué rasgos guían cada decisión, de modo que el modelo pueda interpretarse en la práctica clínica. Se espera que los rasgos wavelet y Radón mejoren a los rasgos de variabilidad cardiaca solos, sobre todo en registros con pocos latidos o con ruido.

**Palabras clave:** fibrilación auricular, electrocardiograma, cuidados intensivos, transformada wavelet, transformada de Radón, explicabilidad, aprendizaje automático.

## Title

Atrial Fibrillation Detection in Intensive Care Electrocardiograms: Reproducing Handcrafted Feature Benchmarks and an Explainable Extension with Wavelet and Radon Transforms

## Abstract

Atrial fibrillation (AF) is the most common arrhythmia in the intensive care unit (ICU), and its automatic detection is hindered by noise, patient motion and the reduced lead set of bedside monitors. This project reproduces the results of Nassar et al. [1], who released a labelled dataset of 596 four lead ICU electrocardiograms (ECGs) and compared classifiers built on handcrafted features, convolutional networks and ECG foundation models. The reproduction focuses on the feature based approach. Signals from the public PhysioNet/CinC 2021 Challenge [2] are filtered with a zero phase 5 to 30 Hz Butterworth bandpass filter and resampled to 240 Hz. R peaks are then detected, and 27 features per lead are computed, including time domain heart rate variability, Poincaré and entropy features. These features train the same models as the original study: k nearest neighbours, multilayer perceptron, support vector machine, logistic regression, random forest, LightGBM, XGBoost and CatBoost. The models are tested on the ICU set with AUROC, AUPRC, F1 score, specificity, balanced accuracy and the Matthews correlation coefficient. The analysis is then extended with tools from the course. The discrete wavelet transform yields subband energies and entropies of the ECG and of the RR interval series, and the continuous wavelet scaleogram describes atrial activity. The Radon transform, applied to recurrence plots and scaleograms, gives orientation features that separate regular from irregular rhythm. Fourier analysis estimates the dominant frequency of fibrillatory waves, and the Cramér Rao lower bound limits the variance of heart rate estimates from 10 s windows. Finally, SHAP values explain which features drive each decision, so that the model can be read in clinical practice. We expect wavelet and Radon features to improve on heart rate variability features alone, mainly on short or noisy recordings.

**Index Terms:** atrial fibrillation, electrocardiogram, intensive care, wavelet transform, Radon transform, explainability, machine learning.

## Artículo base

S. Nassar, N. Maghsoodi, S. Mannina, S. Addas, S. Sibley, G. Fichtinger, D. Pichora, D. Maslove, P. Abolmaesumi y P. Mousavi, «A Dataset and Benchmarks for Atrial Fibrillation Detection from Electrocardiograms of Intensive Care Unit Patients», arXiv:2512.18031v2, 2025. Copia local en paper/Nassar2025_AF_ICU_Abolmaesumi.pdf.

## Datos

1. Competencia PhysioNet/CinC 2021 (12 derivaciones, acceso abierto, licencia CC BY 4.0), de la que se usan las derivaciones I, II, III y V1.
2. Kingston ICU AF Dataset v1.0.0 en PhysioNet (596 registros, 240 Hz, acceso restringido que requiere firmar el acuerdo de uso de datos).
