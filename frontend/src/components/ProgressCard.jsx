import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BADGE_ICONS, levelProgress, nextBadge } from "../utils/gamification";
import ProgressBar from "./ProgressBar";
import "./ProgressCard.css";

function ProgressCard({ data, showLink = true })
{
	const { t } = useTranslation();
	const { progress } = data;
	const { current, needed } = levelProgress(progress);
	const xpText = t("gamification.xpProgress", { current, needed });
	const upcoming = nextBadge(data);

	return (
		<section className="progress-card">
			<span className={`progress-card-icon ${progress.badge ? "" : "progress-card-icon-level"}`.trim()} aria-hidden="true">
				{progress.badge ? BADGE_ICONS[progress.badge] : progress.level}
			</span>
			<div className="progress-card-body">
				<h2>{progress.badge ? t(`gamification.badges.${progress.badge}`) : t("gamification.noBadge")}</h2>
				<p className="progress-card-level">
					{t("gamification.levelLong", { level: progress.level })} · {t("gamification.totalXp", { xp: progress.xp })}
				</p>
				<ProgressBar value={current} max={needed} label={t("gamification.levelProgress")} valueText={xpText} />
				<p className="progress-card-hint">
					{progress.next_level_xp === null
						? t("gamification.maxLevel")
						: `${xpText} ${t("gamification.toNextLevel", { level: progress.level + 1 })}`}
				</p>
				<p className="progress-card-hint">
					{upcoming
						? t("gamification.nextBadge", { badge: t(`gamification.badges.${upcoming.key}`), level: upcoming.level })
						: t("gamification.allBadges")}
				</p>
				{showLink && <Link to="/achievements" className="progress-card-link">{t("gamification.seeAll")}</Link>}
			</div>
		</section>
	);
}

export default ProgressCard;
