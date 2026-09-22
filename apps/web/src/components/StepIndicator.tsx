import styles from "./StepIndicator.module.css";

const STEPS = ["SUBIR", "REVISAR", "FINALIZAR"] as const;
type Step = (typeof STEPS)[number];

interface Props {
  active: Step;
}

export default function StepIndicator({ active }: Props) {
  const activeIndex = STEPS.indexOf(active);

  return (
    <div className={styles.steps}>
      {STEPS.map((step, i) => {
        const isActive = step === active;
        const isDone = i < activeIndex;
        return (
          <div
            key={step}
            className={[
              styles.step,
              isActive ? styles["step--active"] : "",
              isDone ? styles["step--done"] : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <span className={styles.stepLabel}>{step}</span>
          </div>
        );
      })}
    </div>
  );
}
