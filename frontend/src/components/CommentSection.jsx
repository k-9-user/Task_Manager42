import { useEffect, useRef, useState } from "react";
import { getTaskComments, addComment, deleteComment } from "../services/taskService";
import { useTranslation } from "react-i18next";

const REFRESH_INTERVAL_MS = 15000;

function CommentSection({ taskId, currentUserId, isOwner })
{
	const [comments, setComments] = useState([]);
	const [content, setContent] = useState("");
	const [loading, setLoading] = useState(true);
	const [posting, setPosting] = useState(false);
	const [error, setError] = useState("");
	const [refreshError, setRefreshError] = useState(false);
	const refreshState = useRef(null);
	const { t } = useTranslation();

	useEffect(() =>
	{
		const state = { active: true, pending: false, revision: 0, mutations: 0, queued: false };
		setComments([]);
		setContent("");
		setLoading(true);
		setPosting(false);
		setError("");
		setRefreshError(false);

		async function fetchComments()
		{
			if (!state.active)
				return ;
			if (state.pending || state.mutations)
			{
				state.queued = true;
				return ;
			}
			state.pending = true;
			state.queued = false;
			const revision = state.revision;
			try
			{
				const data = await getTaskComments(taskId);
				if (state.active && revision === state.revision)
				{
					setComments(data.comments);
					setRefreshError(false);
				}
			}
			catch
			{
				if (state.active && revision === state.revision)
					setRefreshError(true);
			}
			finally
			{
				state.pending = false;
				if (state.active)
				{
					if (revision === state.revision)
						setLoading(false);
					if (state.queued && !state.mutations)
						fetchComments();
				}
			}
		}
		state.refresh = fetchComments;
		refreshState.current = state;
		fetchComments();
		const interval = setInterval(fetchComments, REFRESH_INTERVAL_MS);
		return () =>
		{
			state.active = false;
			clearInterval(interval);
		};
	}, [taskId]);

	async function handleSubmit(e)
	{
		e.preventDefault();
		if (!content.trim())
		{
			setError(t("error.required"));
			return ;
		}

		const state = refreshState.current;
		if (!state?.active)
			return ;
		const draft = content;
		state.revision++;
		state.mutations++;
		setPosting(true);
		setError("");
		try
		{
			const data = await addComment(taskId, draft.trim());
			if (state.active)
			{
				setComments((current) => [...current, data.comment]);
				setContent((current) => current === draft ? "" : current);
			}
		}
		catch (err)
		{
			if (state.active)
				setError(err.message);
		}
		finally
		{
			state.mutations--;
			state.revision++;
			if (state.active)
			{
				setPosting(false);
				state.refresh();
			}
		}
	}

	async function handleDelete(commentId)
	{
		const state = refreshState.current;
		if (!state?.active)
			return ;
		state.revision++;
		state.mutations++;
		setError("");
		try
		{
			await deleteComment(commentId);
			if (state.active)
				setComments((current) => current.filter((c) => c.id !== commentId));
		}
		catch (err)
		{
			if (state.active)
				setError(err.message);
		}
		finally
		{
			state.mutations--;
			state.revision++;
			if (state.active)
				state.refresh();
		}
	}

	return (
		<div>
			{loading ? (
				<p>{t("loading.load")}</p>
			) : (
				<ul>
					{comments.map((comment) => (
						<li key={comment.id}>
							<strong>{comment.author_username}</strong>
							<p>{comment.content}</p>
							{(comment.author_id === currentUserId || isOwner) && (
								<button onClick={() => handleDelete(comment.id)}>{t("comments.delete")}</button>
							)}
						</li>
					))}
				</ul>
			)}
			<form onSubmit={handleSubmit}>
				<textarea
					value={content}
					onChange={(e) => setContent(e.target.value)}
					placeholder={t("comments.placeholder")}
					aria-label={t("comments.placeholder")}
					maxLength={5000}
				/>
				<button type="submit" disabled={posting}>
					{posting ? t("loading.sending") : t("comments.submit")}
				</button>
			</form>
			{error && <p className="error">{error}</p>}
			{refreshError && <p className="error">{t("comments.refreshError")}</p>}
		</div>
	);
}

export default CommentSection;
