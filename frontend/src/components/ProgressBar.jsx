import "./ProgressBar.css";

function ProgressBar({ value, max, label, valueText, className = "" })
{
	const clamped = Math.min(Math.max(value, 0), max);
	const percent = max > 0 ? Math.round((clamped / max) * 100) : 100;

	return (
		<div
			className={`progress-bar ${className}`.trim()}
			role="progressbar"
			aria-label={label}
			aria-valuemin={0}
			aria-valuemax={max}
			aria-valuenow={clamped}
			aria-valuetext={valueText}
		>
			<div className="progress-bar-fill" style={{ width: `${percent}%` }} />
		</div>
	);
}

export default ProgressBar;
