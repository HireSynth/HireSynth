from .synth_test_prompts import synth_test_n_shot_examples, synth_test_system_prompt
from .synth_test_config import (
    PromptTest,
    LengthTest,
    IndividualPromptTestOutput,
    LengthOperators,
    OutputTestResponse,
    ScoreOptions,
)
from synth_machine.machine_config import ModelConfig
from typing import List
import logging
import json
import openai
import os


def generate(prompt, system_prompt, llm_config: ModelConfig):
    togetherai_client = openai.OpenAI(
        api_key=os.environ.get("TOGETHER_API_KEY"),
        base_url="https://api.together.xyz/v1",
    )
    response = togetherai_client.chat.completions.create(
        model=llm_config.llm_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
        stop=["---", "**Rule**", "assistant"],
    )
    return response.choices[0].message.content


def remove_before_char(s, char):
    index = s.find(char)
    return s[index:] if index != -1 else s


def remove_after_last_char(s, char):
    index = s.rfind(char)
    return s[: index + 1] if index != -1 else s


def test_prompt(
    test_response: str, testcase: PromptTest, llm_config_list: List[ModelConfig]
) -> OutputTestResponse:
    results = []
    full_score = 0
    for llm_config in llm_config_list:
        prompt_response = generate(
            prompt=f"{synth_test_n_shot_examples}[**Rule**: [RULE START]]{testcase.rule}[RULE END]\n**Value:** [VALUE START]{test_response}[VALUE END]\n**Result**:",
            system_prompt=synth_test_system_prompt,
            llm_config=llm_config,
        )
        # Small models sometimes don't follow prompt formats exactly
        prompt_cleaned = remove_after_last_char(
            remove_before_char(prompt_response, "{"), "}"
        )
        try:
            logging.debug(f"Starting model: {llm_config.llm_name}")
            prompt_result = IndividualPromptTestOutput(
                **(json.loads(prompt_cleaned) | {"llm_name": llm_config.llm_name})
            )
        except json.JSONDecodeError:
            logging.warning(
                f"Model: {llm_config.llm_name} failed, removing from selection"
            )
            logging.info(f"Failed Prompt Response: {prompt_cleaned}")
            continue

        match prompt_result.score:
            case ScoreOptions.green:
                full_score += 3
            case ScoreOptions.yellow:
                full_score += 1
            case _:
                pass
        results.append(prompt_result)

    if len(results) == 0:
        raise Exception(
            "All models failed validation, consider reviewing models and/or prompt"
        )
    return OutputTestResponse(
        test="prompt",
        success=full_score >= (testcase.test_value * len(results)),
        score=round(float(full_score) / len(results), 2),
        results=results,
    )


def test_length(value: str | list, config: LengthTest) -> OutputTestResponse:
    length = len(value)
    match config.operator:
        case LengthOperators.equals:
            test_success = config.test_value == length
        case LengthOperators.greater_than | LengthOperators.gt:
            test_success = config.test_value < len(value)
        case LengthOperators.less_than | LengthOperators.lt:
            test_success = config.test_value > len(value)
        case _:
            raise Exception(f"No length test for: {config.operator}")
    return OutputTestResponse(test="length", success=test_success, score=length)
