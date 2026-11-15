import re
import time
from app.search_tool import web_search
from app.agents import (
    research_chain,
    writer_chain,
    critic_chain,
    image_prompt_chain,
    caption_chain
)
from app.image_generator import generate_image_from_api


# =========================================================
# 1. HELPER FUNCTIONS
# =========================================================

def extract_critic_action(critic_feedback):
    """
    Extract APPROVE, REVISE_EXISTING_MEME or GENERATE_NEW_MEME.
    Handles Markdown formatting and line breaks.
    """

    clean_feedback = re.sub(
        r"[*`]",
        "",
        str(critic_feedback)
    ).strip()

    match = re.search(
        r"RECOMMENDED[\s_]*ACTION\s*:\s*"
        r"(GENERATE_NEW_MEME|REVISE_EXISTING_MEME|APPROVE)\b",
        clean_feedback,
        re.IGNORECASE
    )

    return match.group(1).upper() if match else None


def extract_critic_score(critic_feedback):
    """Extract the overall Critic score out of 10."""

    clean_feedback = re.sub(
        r"[*`]",
        "",
        str(critic_feedback)
    )

    match = re.search(
        r"\bSCORE\s*:\s*(\d+(?:\.\d+)?)\s*/\s*10\b",
        clean_feedback,
        re.IGNORECASE
    )

    return float(match.group(1)) if match else None


def extract_problem_type(critic_feedback):
    """Extract the Critic's problem classification."""

    match = re.search(
        r"PROBLEM_TYPE\s*:\s*"
        r"(WEAK_CONCEPT|WEAK_MEME_COPY|VISUAL_DIRECTION|MINOR_ISSUES)\b",
        str(critic_feedback),
        re.IGNORECASE
    )

    return match.group(1).upper() if match else None


def extract_meme_title(draft):
    """Extract the meme title from the Writer output."""

    match = re.search(
        r"MEME\s*TITLE\s*:\s*(.+)",
        str(draft),
        re.IGNORECASE
    )

    return match.group(1).strip() if match else "Untitled Meme"


def extract_meme_text_from_draft(draft):
    """
    Extract Top Text and Bottom Text from the updated
    Writer output format.
    """

    draft = str(draft)

    top_match = re.search(
        r"^\s*Top\s*text\s*:\s*(.*?)"
        r"(?=^\s*Bottom\s*text\s*:|\Z)",
        draft,
        re.IGNORECASE | re.MULTILINE | re.DOTALL
    )

    bottom_match = re.search(
        r"^\s*Bottom\s*text\s*:\s*(.*?)"
        r"(?=^\s*(?:CAPTION|HASHTAGS|MEME\s+TITLE|MEME\s+CONCEPT|VISUAL\s+DESCRIPTION)\s*:|\Z)",
        draft,
        re.IGNORECASE | re.MULTILINE | re.DOTALL
    )

    top_text = top_match.group(1).strip() if top_match else ""
    bottom_text = bottom_match.group(1).strip() if bottom_match else ""

    return top_text, bottom_text


def parse_caption_result(caption_output):
    """
    Parse the Caption Agent output and create
    the complete Instagram caption.
    """

    caption_match = re.search(
        r"CAPTION\s*:\s*(.*?)(?=\n\s*HASHTAGS\s*:|\Z)",
        str(caption_output),
        re.IGNORECASE | re.DOTALL
    )

    hashtags_match = re.search(
        r"HASHTAGS\s*:\s*(.*)",
        str(caption_output),
        re.IGNORECASE | re.DOTALL
    )

    post_caption = (
        caption_match.group(1).strip()
        if caption_match else ""
    )

    hashtag_source = (
        hashtags_match.group(1)
        if hashtags_match else ""
    )

    hashtags = list(dict.fromkeys(
        re.findall(r"#[A-Za-z0-9_]+", hashtag_source)
    ))

    # Always include the page hashtag.
    required_hashtag = "#365DaysOfCramming"

    if not any(
        h.lower() == required_hashtag.lower()
        for h in hashtags
    ):
        hashtags.append(required_hashtag)

    instagram_caption = post_caption

    if hashtags:
        instagram_caption += "\n\n" + " ".join(hashtags)

    return {
        "post_caption": post_caption,
        "hashtags": hashtags,
        "instagram_caption": instagram_caption
    }


# =========================================================
# 2. MAIN MEME GENERATION FUNCTION
# =========================================================

def generate_complete_meme(
    target_audience="College Students",
    platform="Instagram",
    meme_format="Single Image Meme",
    language="Conversational English",
    max_attempts=5,
    cooldown_seconds=5
):



    production_constraints = """
    The meme should be:
    - Relatable to college students.
    - Funny and shareable.
    - Easy to understand.
    - Suitable for Instagram.
    - Based on a clear joke or relatable situation.
    - Visually simple and understandable within seconds.
    """

    # -----------------------------------------------------
    # 3. INITIALIZE VARIABLES
    # -----------------------------------------------------

    current_draft = ""
    previous_draft = ""
    previous_feedback = ""

    writer_feedback = """
    Create a highly relatable and original meme for college students.
    Focus on humour, simplicity, originality and shareability.
    """

    critic_feedback = ""
    research_brief = ""

    attempts = 0

    is_approved = False
    action_error = False

    selected_draft = None
    selected_feedback = None
    selected_score = None
    selected_attempt = None

    selection_reason = None

    # Stores EVERY evaluated draft across all concepts.
    # This is important for fifth-attempt fallback.

    attempt_history = []

    # -----------------------------------------------------
    # 4. INITIAL RESEARCH
    # -----------------------------------------------------

    try:


        search_insights = web_search(
            "latest funny college student relatable meme trends 2026"
        )

        research_brief = research_chain.invoke({
            "target_audience": target_audience,
            "platform": platform,
            "meme_format": meme_format,
            "language": language,
            "production_constraints": (
                production_constraints
                + "\nWeb Search Insights:\n"
                + str(search_insights)
            )
        })


    except Exception as e:


        return {
            "status": "research_failed",
            "approved": False,
            "error": str(e),
            "attempts": 0
        }

    # -----------------------------------------------------
    # 5. WRITER-CRITIC LOOP
    # -----------------------------------------------------

    for attempt_number in range(1, max_attempts + 1):

        attempts = attempt_number


        # ================================================
        # STEP 1: WRITER AGENT
        # ================================================


        try:

            if cooldown_seconds:
                time.sleep(cooldown_seconds)

            current_draft = writer_chain.invoke({
                "research_brief": research_brief,
                "draft": current_draft,
                "feedback": writer_feedback
            })

            current_draft = str(current_draft).strip()

            if not current_draft:
                raise ValueError("Writer returned an empty meme draft.")


        except Exception as e:


            return {
                "status": "writer_failed",
                "approved": False,
                "error": str(e),
                "attempts": attempts,
                "attempt_history": attempt_history,
                "meme_draft": current_draft
            }

        # ================================================
        # STEP 2: CRITIC AGENT
        # ================================================


        try:

            if cooldown_seconds:
                time.sleep(cooldown_seconds)

            critic_feedback = critic_chain.invoke({
                "research_brief": research_brief,
                "previous_draft": previous_draft,
                "draft": current_draft,
                "previous_feedback": previous_feedback
            })

            critic_feedback = str(critic_feedback).strip()


        except Exception as e:


            return {
                "status": "critic_failed",
                "approved": False,
                "error": str(e),
                "attempts": attempts,
                "attempt_history": attempt_history,
                "meme_draft": current_draft
            }

        # ================================================
        # STEP 3: EXTRACT CRITIC DECISION AND SCORE
        # ================================================

        action = extract_critic_action(critic_feedback)

        score = extract_critic_score(critic_feedback)

        problem_type = extract_problem_type(critic_feedback)


        # Save this evaluated draft BEFORE deciding
        # whether to revise or generate a new concept.

        history_item = {
            "attempt": attempts,
            "draft": current_draft,
            "critic_feedback": critic_feedback,
            "action": action,
            "score": score,
            "problem_type": problem_type,
            "research_brief": research_brief
        }

        attempt_history.append(history_item)

        # ================================================
        # STEP 4: HANDLE INVALID CRITIC ACTION
        # ================================================

        if action is None:



            action_error = True

            break

        # ================================================
        # CASE 1: APPROVE
        # ================================================

        if action == "APPROVE":


            is_approved = True

            selected_draft = current_draft
            selected_feedback = critic_feedback
            selected_score = score
            selected_attempt = attempts

            selection_reason = "CRITIC_APPROVED"

            break

        # ================================================
        # CASE 2: GENERATE A NEW MEME CONCEPT
        # ================================================

        elif action == "GENERATE_NEW_MEME":


            # No need to research a concept that cannot
            # receive another evaluation after the last attempt.

            if attempts >= max_attempts:


                break


            try:

                if cooldown_seconds:
                    time.sleep(cooldown_seconds)

                search_insights = web_search(
                    "fresh funny original college student meme ideas "
                    "and relatable situations 2026"
                )

                new_research_context = (
                    production_constraints
                    + "\nWeb Search Insights:\n"
                    + str(search_insights)
                    + "\n\nPrevious Concept to Avoid:\n"
                    + current_draft
                    + "\n\nCritic Feedback on Previous Concept:\n"
                    + critic_feedback
                    + "\n\nIMPORTANT: Generate a genuinely different "
                    "meme concept. Do not repeat the previous joke."
                )

                research_brief = research_chain.invoke({
                    "target_audience": target_audience,
                    "platform": platform,
                    "meme_format": meme_format,
                    "language": language,
                    "production_constraints": new_research_context
                })


            except Exception as e:


                return {
                    "status": "new_research_failed",
                    "approved": False,
                    "error": str(e),
                    "attempts": attempts,
                    "attempt_history": attempt_history
                }

            # IMPORTANT:
            # Reset only the current concept's revision context.
            # Do NOT delete attempt_history.
            # Earlier concepts must remain available for fallback.

            current_draft = ""
            previous_draft = ""
            previous_feedback = ""

            writer_feedback = """
            Create a completely NEW meme using the latest research brief.

            Do not reuse the previous concept or joke.

            Focus on:
            - Strong humour.
            - Originality.
            - College student relatability.
            - Simple visual composition.
            - Shareability.

            Return the required structured meme format.
            """

            continue

        # ================================================
        # CASE 3: REVISE EXISTING MEME
        # ================================================

        elif action == "REVISE_EXISTING_MEME":


            if attempts >= max_attempts:


                break

            # Save the current draft for the next revision.

            previous_draft = current_draft
            previous_feedback = critic_feedback

            # Pass Critic feedback to Writer.

            writer_feedback = critic_feedback


            continue

    # -----------------------------------------------------
    # 6. SELECT THE FINAL MEME
    # -----------------------------------------------------


    # CASE A: Critic explicitly approved a meme.
    # CASE B: Otherwise, select the highest-scoring draft after the final attempt.

    if not is_approved and not action_error and attempts >= max_attempts:


        scored_drafts = [
            item for item in attempt_history
            if item["score"] is not None
        ]

        if not scored_drafts:

            return {
                "status": "no_valid_scores",
                "approved": False,
                "error": "No valid Critic scores were available.",
                "attempts": attempts,
                "attempt_history": attempt_history
            }

        # Highest score wins.
        # If two drafts have equal scores, select the later attempt.

        best_draft = max(
            scored_drafts,
            key=lambda item: (item["score"], item["attempt"])
        )

        selected_draft = best_draft["draft"]
        selected_feedback = best_draft["critic_feedback"]
        selected_score = best_draft["score"]
        selected_attempt = best_draft["attempt"]

        selection_reason = "BEST_SCORE_FALLBACK"



    # CASE C: Invalid Critic action.
    # Do not silently use a draft when the decision parser fails.

    elif not is_approved and action_error:

        return {
            "status": "critic_action_error",
            "approved": False,
            "error": "Critic action could not be extracted.",
            "attempts": attempts,
            "meme_draft": current_draft,
            "critic_feedback": critic_feedback,
            "attempt_history": attempt_history
        }

    # Safety check.

    if selected_draft is None:

        return {
            "status": "no_selected_draft",
            "approved": False,
            "error": "No final meme draft could be selected.",
            "attempts": attempts,
            "attempt_history": attempt_history
        }

    # -----------------------------------------------------
    # 7. EXTRACT SELECTED MEME METADATA
    # -----------------------------------------------------

    meme_title = extract_meme_title(selected_draft)





    # -----------------------------------------------------
    # 8. EXTRACT TOP AND BOTTOM MEME TEXT
    # -----------------------------------------------------


    top_text, bottom_text = extract_meme_text_from_draft(
        selected_draft
    )


    if not top_text and not bottom_text:

        return {
            "status": "meme_text_extraction_failed",
            "approved": is_approved,
            "selection_reason": selection_reason,
            "error": "Could not extract Top Text or Bottom Text.",
            "meme_draft": selected_draft,
            "attempts": attempts
        }

    # -----------------------------------------------------
    # 9. IMAGE PROMPT CREATOR AGENT
    # -----------------------------------------------------


    try:

        if cooldown_seconds:
            time.sleep(cooldown_seconds)

        image_prompt = image_prompt_chain.invoke({
            "approved_meme": selected_draft,
            "top_text": top_text,
            "bottom_text": bottom_text
        })

        image_prompt = str(image_prompt).strip()

        if not image_prompt:
            raise ValueError("Image Prompt Creator returned an empty prompt.")


    except Exception as e:


        return {
            "status": "image_prompt_failed",
            "approved": is_approved,
            "selection_reason": selection_reason,
            "error": str(e),
            "meme_draft": selected_draft,
            "image_prompt": None,
            "attempts": attempts
        }

    # -----------------------------------------------------
    # 10. CLOUDFLARE FLUX IMAGE GENERATION
    # -----------------------------------------------------


    try:

        filename = f"insta_meme_{int(time.time())}.png"

        saved_image = generate_image_from_api(
            prompt_text=image_prompt,
            output_path=filename
        )

        if not saved_image:
            raise RuntimeError("Cloudflare image generation returned no image.")

        image_path = str(saved_image)


    except Exception as e:


        return {
            "status": "image_generation_failed",
            "approved": is_approved,
            "selection_reason": selection_reason,
            "error": str(e),
            "meme_title": meme_title,
            "meme_draft": selected_draft,
            "image_prompt": image_prompt,
            "attempts": attempts
        }

    # -----------------------------------------------------
    # 11. INSTAGRAM CAPTION AGENT
    # -----------------------------------------------------


    try:

        if cooldown_seconds:
            time.sleep(cooldown_seconds)

        caption_output = caption_chain.invoke({
            "target_audience": target_audience,
            "platform": platform,
            "language": language,
            "approved_meme": selected_draft,
            "top_text": top_text,
            "bottom_text": bottom_text
        })


        caption_data = parse_caption_result(caption_output)

        post_caption = caption_data["post_caption"]
        hashtags = caption_data["hashtags"]
        instagram_caption = caption_data["instagram_caption"]

        if not post_caption:

            raise ValueError("Caption Agent did not generate a caption.")


    except Exception as e:


        return {
            "status": "caption_generation_failed",
            "approved": is_approved,
            "selection_reason": selection_reason,
            "error": str(e),
            "meme_title": meme_title,
            "meme_draft": selected_draft,
            "image_path": image_path,
            "image_prompt": image_prompt,
            "attempts": attempts
        }

    # -----------------------------------------------------
    # 12. FINAL RESULT
    # -----------------------------------------------------

    result = {
        "status": "success",

        # True only when the Critic actually approved.
        "approved": is_approved,

        # CRITIC_APPROVED or BEST_SCORE_FALLBACK
        "selection_reason": selection_reason,

        "meme_title": meme_title,
        "meme_draft": selected_draft,

        "top_text": top_text,
        "bottom_text": bottom_text,

        "critic_feedback": selected_feedback,
        "selected_score": selected_score,
        "selected_attempt": selected_attempt,

        "image_prompt": image_prompt,
        "image_path": image_path,

        "post_caption": post_caption,
        "hashtags": hashtags,
        "instagram_caption": instagram_caption,

        "attempts": attempts,

        # Retain the history of every evaluated draft.
        "attempt_history": attempt_history
    }



    return result

