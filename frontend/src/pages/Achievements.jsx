import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import ProgressBar from "../components/ProgressBar";
import ProgressCard from "../components/ProgressCard";
import { getMyProgress } from "../services/gamificationService";
import { BADGE_ICONS, formatDate, tierLabel } from "../utils/gamification";
import "./Achievements.css";

const RULES = ["xp", "levels", "badges", "counts"];

function Achievements()
{
	const { t, i18n } = useTranslation();
	const [data, setData] = useState(null);
	const [error, setError] = useState("");

	useEffect(() =>
	{
		getMyProgress()
			.then(setData)
			.catch((err) => setError(err.message));
	}, []);

	if (error)
		return (<p className="error">{t("error.err")} : {error}</p>);
	if (!data)
		return (<p>{t("loading.load")}</p>);

	return (
		<div className="achievements-page">
			<header className="achievements-header">
				<h1>{t("gamification.title")}</h1>
				<p>{t("gamification.subtitle")}</p>
			</header>
			<ProgressCard data={data} showLink={false} />
			<section className="achievements-section">
				<h2>{t("gamification.badgesTitle")}</h2>
				<ul className="badge-ladder">
					{data.badges.map((badge) => (
						<li key={badge.key} className={badge.awarded_at ? "earned" : "locked"}>
							<span className="badge-ladder-icon" aria-hidden="true">{BADGE_ICONS[badge.key]}</span>
							<strong>{t(`gamification.badges.${badge.key}`)}</strong>
							<span>{t("gamification.badgeLevel", { level: badge.level, xp: badge.xp })}</span>
							<span className="badge-ladder-state">
								{badge.awarded_at
									? t("gamification.earnedOn", { date: formatDate(badge.awarded_at, i18n.language) })
									: t("gamification.locked")}
							</span>
						</li>
					))}
				</ul>
			</section>
			{data.tracks.map((track) => (
				<section key={track.key} className="achievements-section">
					<div className="track-header">
						<h2>{t(`gamification.tracks.${track.key}.name`)}</h2>
						<span className="track-count">{t("gamification.count", { count: track.count })}</span>
					</div>
					<ul className="tier-list">
						{track.achievements.map((achievement, index) => {
							const goal = t(`gamification.tracks.${track.key}.goal`, { count: achievement.threshold });
							const current = Math.min(track.count, achievement.threshold);
							return (
								<li key={achievement.key} className={achievement.unlocked_at ? "unlocked" : "locked"}>
									<div className="tier-heading">
										<strong>{t(`gamification.tracks.${track.key}.name`)} {tierLabel(index)}</strong>
										<span className="tier-xp">{t("gamification.rewardXp", { xp: achievement.xp })}</span>
									</div>
									<p>{goal}</p>
									{achievement.unlocked_at ? (
										<p className="tier-state">
											<span aria-hidden="true">✓ </span>
											{t("gamification.unlockedOn", { date: formatDate(achievement.unlocked_at, i18n.language) })}
										</p>
									) : (
										<>
											<ProgressBar value={current} max={achievement.threshold} label={goal} valueText={`${current} / ${achievement.threshold}`} />
											<p className="tier-state">{current} / {achievement.threshold}</p>
										</>
									)}
								</li>
							);
						})}
					</ul>
				</section>
			))}
			<section className="achievements-section">
				<h2>{t("gamification.rulesTitle")}</h2>
				<ul className="rules-list">
					{RULES.map((rule) => (
						<li key={rule}>{t(`gamification.rules.${rule}`)}</li>
					))}
				</ul>
			</section>
		</div>
	);
}

export default Achievements;
