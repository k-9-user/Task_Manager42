import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ACTIVITY_EVENT } from "../services/api";
import { getMyProgress } from "../services/gamificationService";
import { BADGE_ICONS, levelProgress, newUnlocks, tierLabel } from "../utils/gamification";
import ProgressBar from "./ProgressBar";
import "./GamificationWidget.css";

const REFRESH_DELAY_MS = 300;
const TOAST_DURATION_MS = 6000;

function GamificationWidget()
{
	const { t } = useTranslation();
	const [data, setData] = useState(null);
	const [toasts, setToasts] = useState([]);
	const previous = useRef(null);
	const toastTimers = useRef([]);

	const dismiss = useCallback((id) =>
	{
		setToasts((current) => current.filter((toast) => toast.id !== id));
	}, []);

	const refresh = useCallback(() =>
	{
		getMyProgress()
			.then((next) => {
				const unlocks = previous.current ? newUnlocks(previous.current, next) : [];
				previous.current = next;
				setData(next);
				if (unlocks.length === 0)
					return ;
				const stamped = unlocks.map((unlock) => ({ ...unlock, id: `${unlock.type}-${unlock.key}` }));
				setToasts((current) => [...current, ...stamped]);
				for (const toast of stamped)
					toastTimers.current.push(setTimeout(() => dismiss(toast.id), TOAST_DURATION_MS));
			})
			.catch(() => {});
	}, [dismiss]);

	useEffect(() =>
	{
		let pending = null;
		function scheduleRefresh()
		{
			clearTimeout(pending);
			pending = setTimeout(refresh, REFRESH_DELAY_MS);
		}
		refresh();
		window.addEventListener(ACTIVITY_EVENT, scheduleRefresh);
		return () => {
			clearTimeout(pending);
			window.removeEventListener(ACTIVITY_EVENT, scheduleRefresh);
		};
	}, [refresh]);

	useEffect(() =>
	{
		const timers = toastTimers.current;
		return () => timers.forEach(clearTimeout);
	}, []);

	function toastText(toast)
	{
		if (toast.type === "badge")
			return t("gamification.toast.badge", { badge: t(`gamification.badges.${toast.key}`), level: toast.level });
		if (toast.type === "level")
			return t("gamification.toast.level", { level: toast.level });
		return t("gamification.toast.achievement", {
			name: `${t(`gamification.tracks.${toast.track}.name`)} ${tierLabel(toast.index)}`,
		});
	}

	function toastMark(toast)
	{
		if (toast.type === "badge")
			return <span className="gamification-toast-icon" aria-hidden="true">{BADGE_ICONS[toast.key]}</span>;
		const label = toast.type === "level"
			? t("gamification.levelShort", { level: toast.level })
			: t("gamification.rewardXp", { xp: toast.xp });
		return <span className="gamification-toast-chip" aria-hidden="true">{label}</span>;
	}

	const badge = data?.progress.badge;
	const { current, needed } = data ? levelProgress(data.progress) : { current: 0, needed: 1 };
	const xpText = t("gamification.xpProgress", { current, needed });

	return (
		<>
			{data && (
				<Link to="/achievements" className="gamification-widget">
					<span className="gamification-widget-title">
						{badge && <span aria-hidden="true">{BADGE_ICONS[badge]}</span>}
						{badge ? t(`gamification.badges.${badge}`) : t("gamification.noBadge")}
					</span>
					<span className="gamification-widget-level">{t("gamification.levelLong", { level: data.progress.level })}</span>
					<ProgressBar value={current} max={needed} label={t("gamification.levelProgress")} valueText={xpText} />
					<span className="gamification-widget-xp">
						{data.progress.next_level_xp === null ? t("gamification.maxLevel") : xpText}
					</span>
				</Link>
			)}
			<div className="gamification-toasts" role="status" aria-live="polite">
				{toasts.map((toast) => (
					<div key={toast.id} className="gamification-toast">
						{toastMark(toast)}
						<p>{toastText(toast)}</p>
						<button type="button" onClick={() => dismiss(toast.id)} aria-label={t("gamification.toast.close")}>✕</button>
					</div>
				))}
			</div>
		</>
	);
}

export default GamificationWidget;
