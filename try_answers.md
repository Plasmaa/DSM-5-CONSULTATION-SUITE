# DSM-5 Clinical Assistant — 15 Pipeline Verification Answers
Model: `qwen3:8b` (think: false, num_ctx: 8192, temperature: 0.1)

---
## 1. [Q01] (LOOKUP)
**Question:**
> What are the diagnostic criteria for Generalized Anxiety Disorder?

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `Agoraphobia` | Section: `Diagnostic Criteria` | Page: `p.255` | Score: `0.7850`
- **Source 2**: `Generalized Anxiety Disorder` | Section: `Differential Diagnosis` | Page: `p.263` | Score: `0.7783`
- **Source 3**: `Unspecified Anxiety Disorder` | Section: `Diagnostic Criteria` | Page: `p.271` | Score: `0.7674`
- **Source 4**: `Generalized Anxiety Disorder` | Section: `Diagnostic Features` | Page: `p.260` | Score: `0.7645`
- **Source 5**: `Generalized Anxiety Disorder` | Section: `Comorbidity` | Page: `p.264` | Score: `0.7636`

### Assistant Response:
The diagnostic criteria for Generalized Anxiety Disorder (GAD) include the following:

1. Excessive anxiety and worry, occurring on more days than not for at least 6 months, about a number of life circumstances, such as work or school performance, social interactions, health, finances, etc. The individual finds it difficult to control the worry.

2. The anxiety and worry are associated with at least three of the following symptoms:
   - Restlessness or feeling keyed up or on edge
   - Being easily fatigued
   - Difficulty concentrating or mind going blank
   - Irritability
   - Muscle tension
   - Sleep disturbance (e.g., difficulty falling asleep, staying asleep, or restless sleep)

3. The anxiety, worry, or physical symptoms cause clinically significant distress or impairment in social, occupational, or other important areas of functioning.

4. The disturbance is not attributable to the physiological effects of a substance (e.g., a drug of abuse, a medication) or another medical condition.

5. The disturbance is not better explained by another mental disorder (e.g., panic disorder, obsessive-compulsive disorder, posttraumatic stress disorder, or a mood disorder).

[Cite: Generalized Anxiety Disorder (300.02 (F41.1)), p.260, Section: Diagnostic Features]

---
## 2. [Q03] (LOOKUP)
**Question:**
> How many symptoms from Criterion A must be present to diagnose Major Depressive Disorder, and for how long?

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `Major Depressive Disorder` | Section: `Diagnostic Features` | Page: `p.200` | Score: `0.7899`
- **Source 2**: `Persistent Depressive Disorder (Dysthymia)` | Section: `Diagnostic Criteria` | Page: `p.206` | Score: `0.7848`
- **Source 3**: `Persistent Depressive Disorder (Dysthymia)` | Section: `Diagnostic Criteria` | Page: `p.206` | Score: `0.7835`
- **Source 4**: `Major Depressive Disorder` | Section: `Differential Diagnosis` | Page: `p.205` | Score: `0.7764`
- **Source 5**: `Specifiers for Depressive Disorders` | Section: `Diagnostic Criteria` | Page: `p.222` | Score: `0.7667`

### Assistant Response:
To diagnose Major Depressive Disorder, the individual must experience either depressed mood or loss of interest or pleasure in nearly all activities (Criterion A). Additionally, the individual must experience at least four additional symptoms from the list of possible symptoms, with the exception of weight change and suicidal ideation, which can be present once [Major Depressive Disorder, Section: Diagnostic Features, p.200]. These symptoms must be present nearly every day for at least 2 consecutive weeks, and the episode must be accompanied by clinically significant distress or impairment in social, occupational, or other important areas of functioning [Major Depressive Disorder, Section: Diagnostic Features, p.200].

---
## 3. [Q05] (LOOKUP)
**Question:**
> What are the diagnostic criteria for Panic Disorder according to DSM-5?

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `General DSM-5` | Section: `Differential Diagnosis` | Page: `p.250` | Score: `0.7746`
- **Source 2**: `Panic Disorder` | Section: `Diagnostic Criteria` | Page: `p.246` | Score: `0.7657`
- **Source 3**: `Agoraphobia` | Section: `Diagnostic Criteria` | Page: `p.255` | Score: `0.7637`
- **Source 4**: `Panic Attack Specifier` | Section: `Diagnostic Criteria` | Page: `p.252` | Score: `0.7604`
- **Source 5**: `Panic Disorder` | Section: `Diagnostic Features` | Page: `p.247` | Score: `0.7570`

### Assistant Response:
The diagnostic criteria for Panic Disorder according to DSM-5 include the following:

1. **Recurrent unexpected panic attacks**: The individual must experience recurrent panic attacks that are not expected by the context (e.g., not provoked by phobic situations, exercise, or other triggers). [Panic Disorder, Diagnostic Criteria, p.246]

2. **Persistent concern or worry about additional attacks**: The individual must have persistent concern about having additional panic attacks or about the consequences of the attacks (e.g., losing control, having a heart attack, "going crazy"). [Panic Disorder, Diagnostic Criteria, p.246]

3. **Maladaptive changes in behavior or physiological symptoms**: The individual must have maladaptive changes in behavior or physiological symptoms related to the attacks, such as avoidance of places or situations where panic attacks might occur. [Panic Disorder, Diagnostic Criteria, p.246]

4. **Not better explained by another mental disorder**: The disturbance is not better explained by the symptoms of another mental disorder (e.g., panic attacks that occur only in response to feared social situations, phobic objects, or traumatic reminders). [Panic Disorder, Diagnostic Criteria, p.246]

5. **Not attributable to the physiological effects of a substance**: The panic attacks are not attributable to the physiological effects of a substance (e.g., a drug of abuse, a medication). [Panic Disorder, Diagnostic Criteria, p.246]

---
## 4. [Q07] (LOOKUP)
**Question:**
> What are the core diagnostic features and required duration for Schizophrenia Criterion A?

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `General DSM-5` | Section: `Diagnostic Features` | Page: `p.138` | Score: `0.8023`
- **Source 2**: `General DSM-5` | Section: `Diagnostic Features` | Page: `p.135` | Score: `0.8015`
- **Source 3**: `General DSM-5` | Section: `Diagnostic Features` | Page: `p.144` | Score: `0.7985`
- **Source 4**: `General DSM-5` | Section: `Diagnostic Features` | Page: `p.132` | Score: `0.7865`
- **Source 5**: `General DSM-5` | Section: `Diagnostic Features` | Page: `p.130` | Score: `0.7842`

### Assistant Response:
The core diagnostic features for Schizophrenia Criterion A include the presence of at least two symptoms from the following: delusions (Criterion Al), hallucinations (Criterion A2), disorganized speech (Criterion A3), grossly disorganized or catatonic behavior (Criterion A4), and negative symptoms (Criterion A5). At least one of these symptoms must be the clear presence of delusions, hallucinations, or disorganized speech. 

The required duration for Schizophrenia Criterion A is that these symptoms must be present for a significant portion of time during a 1-month period or longer. If the active-phase symptoms remit within a month in response to treatment, Criterion A is still met if the clinician estimates that they would have persisted in the absence of treatment [Schizophrenia, Section: Diagnostic Features, p.138].

---
## 5. [Q12] (LOOKUP)
**Question:**
> What are the diagnostic criteria for Obsessive-Compulsive Disorder regarding obsessions and compulsions?

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `Obsessive-Compulsive Disorder` | Section: `Diagnostic Criteria` | Page: `p.274` | Score: `0.8255`
- **Source 2**: `Obsessive-Compulsive Disorder` | Section: `Diagnostic Criteria` | Page: `p.274` | Score: `0.8114`
- **Source 3**: `Obsessive-Compulsive Disorder` | Section: `Diagnostic Features` | Page: `p.275` | Score: `0.8097`
- **Source 4**: `Obsessive-Compulsive Disorder` | Section: `Diagnostic Criteria` | Page: `p.274` | Score: `0.7963`
- **Source 5**: `Unspecified Anxiety Disorder` | Section: `Diagnostic Criteria` | Page: `p.271` | Score: `0.7880`

### Assistant Response:
The diagnostic criteria for Obsessive-Compulsive Disorder (OCD) regarding obsessions and compulsions are as follows:

A. Presence of obsessions, compulsions, or both:
Obsessions are defined by (1) and (2):
1. Recurrent and persistent thoughts, urges, or images that are experienced, at some time during the disturbance, as intrusive and unwanted, and that in most individuals cause marked anxiety or distress.
2. The individual attempts to ignore or suppress such thoughts, urges, or images, or to neutralize them with some other thought or action (i.e., by performing a compulsion).
Compulsions are defined by (1) and (2):
1. Repetitive behaviors (e.g., hand washing, ordering, checking) or mental acts (e.g., praying, counting, repeating words silently) that the individual feels driven to perform in response to an obsession or according to rules that must be applied rigidly.
2. The behaviors or mental acts are aimed at preventing or reducing anxiety or distress, or preventing some dreaded event or situation; however, these behaviors or mental acts are not connected in a realistic way with what they are designed to neutralize or prevent, or are clearly excessive. [Obsessive-Compulsive Disorder (300.3 (F42)), p.274, Section: Diagnostic Criteria]

---
## 6. [Q41] (VIGNETTE)
**Question:**
> A 9-year-old boy exhibits persistent patterns of inattention, difficulty sustaining focus on school tasks, frequent careless mistakes, losing pencils, and inability to organize activities across home and school for the past 8 months.

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `Attention-Deficit/Hyperactivity Disorder` | Section: `Diagnostic Criteria` | Page: `p.97` | Score: `0.7326`
- **Source 2**: `Attention-Deficit/Hyperactivity Disorder` | Section: `Development and Course` | Page: `p.100` | Score: `0.6759`
- **Source 3**: `Attention-Deficit/Hyperactivity Disorder` | Section: `Diagnostic Criteria` | Page: `p.97` | Score: `0.6608`
- **Source 4**: `Attention-Deficit/Hyperactivity Disorder` | Section: `Diagnostic Features` | Page: `p.99` | Score: `0.6606`
- **Source 5**: `Specific Learning Disorder` | Section: `Diagnostic Criteria` | Page: `p.104` | Score: `0.6550`

### Assistant Response:
The described symptoms align with the diagnostic criteria for **Attention-Deficit/Hyperactivity Disorder (ADHD)**. Specifically, the child exhibits **inattention** as defined by the DSM-5. The symptoms include:

- **Failing to give close attention to details or making careless mistakes** in schoolwork [ADHD, Section: Diagnostic Criteria, p.97, criterion 1a].
- **Difficulty sustaining attention in tasks or play activities** [ADHD, Section: Diagnostic Criteria, p.97, criterion 1b].
- **Losing things necessary for tasks or activities** [ADHD, Section: Diagnostic Criteria, p.97, criterion 1g].
- **Difficulty organizing tasks and activities** [ADHD, Section: Diagnostic Criteria, p.97, criterion 1e].

These symptoms have persisted for at least 6 months and are inconsistent with developmental level, impacting social and academic functioning. The DSM-5 specifies that for children aged 6–12, **six** symptoms are required for a diagnosis of inattention [ADHD, Section: Diagnostic Criteria, p.97]. The described symptoms meet this threshold.

---
## 7. [Q44] (VIGNETTE)
**Question:**
> A 45-year-old man reports 3 weeks of pervasive depressed mood, anhedonia, unintended weight loss, psychomotor agitation, fatigue, feelings of worthlessness, and diminished concentration nearly every day.

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `Major Depressive Disorder` | Section: `Diagnostic Criteria` | Page: `p.198` | Score: `0.7264`
- **Source 2**: `Bipolar II Disorder` | Section: `Diagnostic Criteria` | Page: `p.170` | Score: `0.7131`
- **Source 3**: `Depressive Episodes With Short-Duration Hypomania` | Section: `Proposed Criteria` | Page: `p.812` | Score: `0.7060`
- **Source 4**: `Bipolar I Disorder` | Section: `Diagnostic Criteria` | Page: `p.161` | Score: `0.7000`
- **Source 5**: `Depressive Episodes With Short-Duration Hypomania` | Section: `Proposed Criteria` | Page: `p.812` | Score: `0.6769`

### Assistant Response:
The symptoms described—pervasive depressed mood, anhedonia, unintended weight loss, psychomotor agitation, fatigue, feelings of worthlessness, and diminished concentration nearly every day—meet the criteria for Major Depressive Disorder. Specifically, the individual exhibits at least five symptoms (depressed mood, anhedonia, weight loss, psychomotor agitation, fatigue, and feelings of worthlessness), which are consistent with the diagnostic criteria for Major Depressive Disorder. [Major Depressive Disorder, Section: Diagnostic Criteria, p.198]

---
## 8. [Q45] (VIGNETTE)
**Question:**
> A 24-year-old college student presents with recurrent sudden surges of intense fear with heart palpitations, sweating, trembling, dizziness, and fear of losing control, followed by persistent worry for over 2 months about future attacks.

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `Panic Disorder` | Section: `Diagnostic Criteria` | Page: `p.246` | Score: `0.7211`
- **Source 2**: `Separation Anxiety Disorder` | Section: `Diagnostic Features` | Page: `p.229` | Score: `0.6809`
- **Source 3**: `Generalized Anxiety Disorder` | Section: `Associated Features Supporting Diagnosis` | Page: `p.261` | Score: `0.6805`
- **Source 4**: `Specific Phobia` | Section: `Associated Features Supporting Diagnosis` | Page: `p.237` | Score: `0.6783`
- **Source 5**: `Panic Attack Specifier` | Section: `Diagnostic Criteria` | Page: `p.252` | Score: `0.6783`

### Assistant Response:
The clinical presentation is consistent with **Panic Disorder**. The individual experiences **recurrent unexpected panic attacks**, characterized by an **abrupt surge of intense fear or discomfort** with **four or more symptoms** (e.g., heart palpitations, sweating, trembling, dizziness, fear of losing control) [Panic Disorder, Section: Diagnostic Criteria, p.246]. Additionally, there is **persistent concern or worry about additional panic attacks** for **more than 1 month** [Panic Disorder, Section: Diagnostic Criteria, p.246]. These features meet the diagnostic criteria for **Panic Disorder**.

---
## 9. [Q48] (VIGNETTE)
**Question:**
> A 27-year-old accountant experiences intense fear and avoidance of public speaking, eating in front of colleagues, and group meetings, fearing scrutiny or humiliation, lasting over 8 months.

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `Social Anxiety Disorder (Social Phobia)` | Section: `Development and Course` | Page: `p.243` | Score: `0.6086`
- **Source 2**: `Social Anxiety Disorder (Social Phobia)` | Section: `Diagnostic Criteria` | Page: `p.240` | Score: `0.6026`
- **Source 3**: `Social Anxiety Disorder (Social Phobia)` | Section: `Diagnostic Features` | Page: `p.241` | Score: `0.5967`
- **Source 4**: `Agoraphobia` | Section: `Associated Features Supporting Diagnosis` | Page: `p.257` | Score: `0.5927`
- **Source 5**: `Agoraphobia` | Section: `Diagnostic Criteria` | Page: `p.255` | Score: `0.5892`

### Assistant Response:
The individual's symptoms are consistent with **Social Anxiety Disorder (Social Phobia)**. The fear and avoidance of public speaking, eating in front of colleagues, and group meetings, along with the fear of scrutiny or humiliation, meet the diagnostic criteria for social anxiety disorder. These situations involve exposure to possible scrutiny by others, and the fear is out of proportion to the actual threat posed by the social situations [Social Anxiety Disorder (Social Phobia), Diagnostic Criteria, p.240]. The symptoms have persisted for over 8 months, which meets the duration criterion of at least 6 months [Social Anxiety Disorder (Social Phobia), Diagnostic Criteria, p.240]. Additionally, the fear and avoidance cause clinically significant distress or impairment in social, occupational, or other important areas of functioning [Social Anxiety Disorder (Social Phobia), Diagnostic Criteria, p.240].

---
## 10. [Q22] (DIFFERENTIAL)
**Question:**
> What is the differential diagnosis between Social Anxiety Disorder and Agoraphobia?

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `Agoraphobia` | Section: `Differential Diagnosis` | Page: `p.258` | Score: `0.8373`
- **Source 2**: `Agoraphobia` | Section: `Diagnostic Criteria` | Page: `p.255` | Score: `0.8232`
- **Source 3**: `Social Anxiety Disorder (Social Phobia)` | Section: `Differential Diagnosis` | Page: `p.244` | Score: `0.8041`
- **Source 4**: `Social Anxiety Disorder (Social Phobia)` | Section: `Differential Diagnosis` | Page: `p.244` | Score: `0.7998`
- **Source 5**: `Agoraphobia` | Section: `Differential Diagnosis` | Page: `p.258` | Score: `0.7956`

### Assistant Response:
The differential diagnosis between Social Anxiety Disorder and Agoraphobia is based primarily on the situational clusters that trigger fear, anxiety, or avoidance and the cognitive ideation. In social anxiety disorder, the focus is on fear of being negatively evaluated by others, whereas in agoraphobia, the focus is on panic-like symptoms or other incapacitating or embarrassing symptoms in the feared situations. Individuals with agoraphobia may fear and avoid social situations (e.g., going to a movie) because escape might be difficult or help might not be available in the event of incapacitation or panic-like symptoms, whereas individuals with social anxiety disorder are most fearful of scrutiny by others. Moreover, individuals with social anxiety disorder are likely to be calm when left entirely alone, which is often not the case in agoraphobia [Social Anxiety Disorder (Social Phobia), p.244, Section: Differential Diagnosis].

---
## 11. [Q24] (DIFFERENTIAL)
**Question:**
> What distinguishes Posttraumatic Stress Disorder from Acute Stress Disorder and Adjustment Disorder?

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `General DSM-5` | Section: `Differential Diagnosis` | Page: `p.316` | Score: `0.8250`
- **Source 2**: `Acute Stress Disorder` | Section: `Differential Diagnosis` | Page: `p.322` | Score: `0.8248`
- **Source 3**: `Unspecified: For maladaptive reactions that are not classifiable as one` | Section: `Differential Diagnosis` | Page: `p.325` | Score: `0.8117`
- **Source 4**: `Acute Stress Disorder` | Section: `Diagnostic Features` | Page: `p.318` | Score: `0.7597`
- **Source 5**: `Acute Stress Disorder` | Section: `Differential Diagnosis` | Page: `p.322` | Score: `0.7442`

### Assistant Response:
Posttraumatic Stress Disorder (PTSD) is distinguished from Acute Stress Disorder (ASD) and Adjustment Disorder by the timing of symptom onset, duration, and symptom profile. 

PTSD is diagnosed when symptoms persist for more than 1 month following exposure to a traumatic event, whereas ASD is diagnosed only if symptoms occur within 1 month of the traumatic event and resolve within that 1-month period [Acute Stress Disorder, Section: Differential Diagnosis, p.322]. If symptoms persist beyond 1 month and meet PTSD criteria, the diagnosis is changed from ASD to PTSD.

Adjustment Disorder, on the other hand, is diagnosed when the stressor can be of any severity rather than the severity and type required by Criterion A of PTSD or ASD. It is also diagnosed when the symptom pattern of PTSD or ASD occurs in response to a stressor that does not meet Criterion A (e.g., spouse leaving, being fired). Adjustment Disorder can be diagnosed immediately and persist up to 6 months after exposure to the traumatic event, whereas ASD can only occur between 3 days and 1 month after exposure to the stressor, and PTSD cannot be diagnosed until at least 1 month has passed since the traumatic event [General DSM-5, Section: Differential Diagnosis, p.316]. 

In addition, the required symptom profile for PTSD and ASD differentiates them from Adjustment Disorder. An Adjustment Disorder may be diagnosed following a traumatic event when an individual exhibits symptoms of either ASD or PTSD that do not meet or exceed the diagnostic threshold for either disorder [Unspecified: For maladaptive reactions that are not classifiable as one, Section: Differential Diagnosis, p.325].

---
## 12. [Q26] (DIFFERENTIAL)
**Question:**
> What is the differential diagnosis between Schizoaffective Disorder, Schizophrenia, and Mood Disorders with psychotic features?

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `General DSM-5` | Section: `Differential Diagnosis` | Page: `p.147` | Score: `0.8518`
- **Source 2**: `General DSM-5` | Section: `Development and Course` | Page: `p.146` | Score: `0.8238`
- **Source 3**: `General DSM-5` | Section: `Differential Diagnosis` | Page: `p.147` | Score: `0.8181`
- **Source 4**: `General DSM-5` | Section: `Associated Features Supporting Diagnosis` | Page: `p.145` | Score: `0.8149`
- **Source 5**: `General DSM-5` | Section: `Diagnostic Features` | Page: `p.144` | Score: `0.8112`

### Assistant Response:
The differential diagnosis between Schizoaffective Disorder, Schizophrenia, and Mood Disorders with Psychotic Features is based on the presence and duration of psychotic symptoms relative to mood symptoms. 

Schizoaffective Disorder is distinguished from Schizophrenia by the presence of a major mood episode (either depressive or manic) that occurs concurrently with psychotic symptoms. Criterion C for Schizoaffective Disorder specifies that mood symptoms meeting the criteria for a major mood episode must be present for the majority of the total duration of the illness. In contrast, Schizophrenia does not require the presence of a major mood episode, and psychotic symptoms are not necessarily associated with mood episodes [Schizoaffective Disorder, Section: Differential Diagnosis, p.147].

Schizoaffective Disorder is also differentiated from Mood Disorders with Psychotic Features by the presence of prominent delusions and/or hallucinations for at least 2 weeks in the absence of a major mood episode. In Mood Disorders with Psychotic Features, the psychotic features primarily occur during the mood episode(s) [Schizoaffective Disorder, Section: Differential Diagnosis, p.147].

---
## 13. [Q33] (OUT_OF_SCOPE)
**Question:**
> What is the recommended starting dose and titration schedule for Sertraline in treating depression?

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `Other Medication-Induced Movement Disorder` | Section: `Diagnostic Features` | Page: `p.744` | Score: `0.6291`
- **Source 2**: `Substance/Medication-Induced Depressive Disorder` | Section: `Risk and Prognostic Factors` | Page: `p.216` | Score: `0.6267`
- **Source 3**: `Sedative, Hypnotic, or Anxiolytic Use Disorder` | Section: `Diagnostic Criteria` | Page: `p.584` | Score: `0.6240`
- **Source 4**: `Substance/Medication-Induced Depressive Disorder` | Section: `Risk and Prognostic Factors` | Page: `p.216` | Score: `0.6234`
- **Source 5**: `Substance/Medication-Induced Depressive Disorder` | Section: `Development and Course` | Page: `p.216` | Score: `0.6137`

### Assistant Response:
Not found in the retrieved DSM-5 sections.

---
## 14. [Q35] (OUT_OF_SCOPE)
**Question:**
> What are the first-line cognitive behavioral therapy exposure techniques for snake phobia?

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `Specific Phobia` | Section: `Associated Features Supporting Diagnosis` | Page: `p.237` | Score: `0.6281`
- **Source 2**: `Specific Phobia` | Section: `Diagnostic Features` | Page: `p.236` | Score: `0.6136`
- **Source 3**: `Specific Phobia` | Section: `Diagnostic Criteria` | Page: `p.235` | Score: `0.6095`
- **Source 4**: `Specifiers for Depressive Disorders` | Section: `Diagnostic Criteria` | Page: `p.222` | Score: `0.6031`
- **Source 5**: `Specific Phobia` | Section: `Development and Course` | Page: `p.237` | Score: `0.6024`

### Assistant Response:
The provided DSM-5 sections do not specifically address first-line cognitive behavioral therapy (CBT) exposure techniques for snake phobia. Therefore, the answer is:

Not found in the retrieved DSM-5 sections.

---
## 15. [Q100] (OUT_OF_SCOPE)
**Question:**
> What is the mathematical proof of the Nyquist-Shannon sampling theorem in digital signal processing?

### Retrieved DSM-5 Sources (Top-5):
- **Source 1**: `I g g` | Section: `Diagnostic Criteria` | Page: `p.772` | Score: `0.5493`
- **Source 2**: `I 2 I` | Section: `Diagnostic Criteria` | Page: `p.72` | Score: `0.4955`
- **Source 3**: `X S2 υ '` | Section: `Diagnostic Criteria` | Page: `p.74` | Score: `0.4935`
- **Source 4**: `S I i -ïi S` | Section: `Diagnostic Criteria` | Page: `p.74` | Score: `0.4875`
- **Source 5**: `Sleep terror type` | Section: `Gender-Related Diagnostic Issues` | Page: `p.436` | Score: `0.4854`

### Assistant Response:
The question is outside the scope of the provided DSM-5 sections. Not found in the retrieved DSM-5 sections.

---
