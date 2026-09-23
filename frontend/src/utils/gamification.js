export const BADGE_ICONS = {
	planner: "📋",
	organizer: "🗂️",
	achiever: "🏅",
	strategist: "🧭",
	grandmaster: "👑",
};

const TIERS = ["I", "II", "III", "IV", "V", "VI"];

export function tierLabel(index)
{
	return TIERS[index] ?? String(index + 1);
}

export function levelProgress(progress)
{
	if (progress.next_level_xp === null)
		return { current: 1, needed: 1 };
	return {
		current: progress.xp - progress.level_xp,
		needed: progress.next_level_xp - progress.level_xp,
	};
}

export function nextBadge(data)
{
	return data.badges.find((badge) => badge.level > data.progress.level) ?? null;
}

function unlockedAchievements(data)
{
	return data.tracks.flatMap((track) =>
		track.achievements
			.map((achievement, index) => ({ ...achievement, track: track.key, index }))
			.filter((achievement) => achievement.unlocked_at)
	);
}

export function newUnlocks(before, after)
{
	const known = new Set(unlockedAchievements(before).map((achievement) => achievement.key));
	const earned = new Set(before.badges.filter((badge) => badge.awarded_at).map((badge) => badge.key));
	const level = after.progress.level;
	const achievements = unlockedAchievements(after)
		.filter((achievement) => !known.has(achievement.key))
		.map((achievement) => ({ type: "achievement", ...achievement }));
	const badges = after.badges
		.filter((badge) => badge.awarded_at && !earned.has(badge.key))
		.map((badge) => ({ type: "badge", key: badge.key, level }));
	const levelUp = badges.length === 0 && level > before.progress.level
		? [{ type: "level", key: String(level), level }]
		: [];
	return [...achievements, ...levelUp, ...badges];
}

export function formatDate(value, language)
{
	return new Date(value).toLocaleDateString(language, { year: "numeric", month: "long", day: "numeric" });
}
