# SPDX-FileCopyrightText: 2023-present deepset GmbH <info@deepset.ai>
#
# SPDX-License-Identifier: Apache-2.0
import logging
from typing import Any, Dict, List, Optional, Union

from haystack import component, default_from_dict, default_to_dict
from haystack.dataclasses import Document
from haystack.document_stores.types import FilterPolicy
from haystack.document_stores.types.filter_policy import apply_filter_policy
from haystack_integrations.document_stores.opensearch import OpenSearchDocumentStore

logger = logging.getLogger(__name__)


@component
class OpenSearchBM25Retriever:
    def __init__(
        self,
        *,
        document_store: OpenSearchDocumentStore,
        filters: Optional[Dict[str, Any]] = None,
        fuzziness: str = "AUTO",
        top_k: int = 10,
        scale_score: bool = False,
        all_terms_must_match: bool = False,
        filter_policy: Union[str, FilterPolicy] = FilterPolicy.REPLACE,
        custom_query: Optional[Dict[str, Any]] = None,
        raise_on_failure: bool = True,
    ):
        """
        Create the OpenSearchBM25Retriever component.

        :param document_store: An instance of OpenSearchDocumentStore.
        :param filters: Filters applied to the retrieved Documents. Defaults to None.
        :param fuzziness: Fuzziness parameter for full-text queries. Defaults to "AUTO".
        :param top_k: Maximum number of Documents to return, defaults to 10
        :param scale_score: Whether to scale the score of retrieved documents between 0 and 1.
            This is useful when comparing documents across different indexes. Defaults to False.
        :param all_terms_must_match: If True, all terms in the query string must be present in the retrieved documents.
            This is useful when searching for short text where even one term can make a difference. Defaults to False.
        :param filter_policy: Policy to determine how filters are applied.
        :param custom_query: The query containing a mandatory `$query` and an optional `$filters` placeholder

            **An example custom_query:**

            ```python
            {
                "query": {
                    "bool": {
                        "should": [{"multi_match": {
                            "query": "$query",                 // mandatory query placeholder
                            "type": "most_fields",
                            "fields": ["content", "title"]}}],
                        "filter": "$filters"                  // optional filter placeholder
                    }
                }
            }
            ```

        **For this custom_query, a sample `run()` could be:**

        ```python
        retriever.run(query="Why did the revenue increase?",
                        filters={"years": ["2019"], "quarters": ["Q1", "Q2"]})
        ```
        :param raise_on_failure:
            Whether to raise an exception if the API call fails. Otherwise log a warning and return an empty list.

        :raises ValueError: If `document_store` is not an instance of OpenSearchDocumentStore.

        """
        if not isinstance(document_store, OpenSearchDocumentStore):
            msg = "document_store must be an instance of OpenSearchDocumentStore"
            raise ValueError(msg)

        self._document_store = document_store
        self._filters = filters or {}
        self._fuzziness = fuzziness
        self._top_k = top_k
        self._scale_score = scale_score
        self._all_terms_must_match = all_terms_must_match
        self._filter_policy = (
            filter_policy if isinstance(filter_policy, FilterPolicy) else FilterPolicy.from_str(filter_policy)
        )
        self._custom_query = custom_query
        self._raise_on_failure = raise_on_failure

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializes the component to a dictionary.

        :returns:
            Dictionary with serialized data.
        """
        return default_to_dict(
            self,
            filters=self._filters,
            fuzziness=self._fuzziness,
            top_k=self._top_k,
            scale_score=self._scale_score,
            document_store=self._document_store.to_dict(),
            filter_policy=self._filter_policy.value,
            custom_query=self._custom_query,
            raise_on_failure=self._raise_on_failure,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OpenSearchBM25Retriever":
        """
        Deserializes the component from a dictionary.

        :param data:
            Dictionary to deserialize from.

        :returns:
            Deserialized component.
        """
        data["init_parameters"]["document_store"] = OpenSearchDocumentStore.from_dict(
            data["init_parameters"]["document_store"]
        )
        data["init_parameters"]["filter_policy"] = FilterPolicy.from_str(data["init_parameters"]["filter_policy"])
        return default_from_dict(cls, data)

    @component.output_types(documents=List[Document])
    def run(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        all_terms_must_match: Optional[bool] = None,
        top_k: Optional[int] = None,
        fuzziness: Optional[str] = None,
        scale_score: Optional[bool] = None,
        custom_query: Optional[Dict[str, Any]] = None,
    ):
        """
        Retrieve documents using BM25 retrieval.

        :param query: The query string
        :param filters: Filters applied to the retrieved Documents. The way runtime filters are applied depends on
                        the `filter_policy` chosen at retriever initialization. See init method docstring for more
                        details.
        :param all_terms_must_match: If True, all terms in the query string must be present in the retrieved documents.
        :param top_k: Maximum number of Documents to return.
        :param fuzziness: Fuzziness parameter for full-text queries.
        :param scale_score: Whether to scale the score of retrieved documents between 0 and 1.
            This is useful when comparing documents across different indexes.
        :param custom_query: The query containing a mandatory `$query` and an optional `$filters` placeholder

            **An example custom_query:**

            ```python
            {
                "query": {
                    "bool": {
                        "should": [{"multi_match": {
                            "query": "$query",                 // mandatory query placeholder
                            "type": "most_fields",
                            "fields": ["content", "title"]}}],
                        "filter": "$filters"                  // optional filter placeholder
                    }
                }
            }
            ```

        **For this custom_query, a sample `run()` could be:**

        ```python
        retriever.run(query="Why did the revenue increase?",
                        filters={"years": ["2019"], "quarters": ["Q1", "Q2"]})
        ```

        :returns:
            A dictionary containing the retrieved documents with the following structure:
            - documents: List of retrieved Documents.

        """
        filters = apply_filter_policy(self._filter_policy, self._filters, filters)

        if filters is None:
            filters = self._filters
        if all_terms_must_match is None:
            all_terms_must_match = self._all_terms_must_match
        if top_k is None:
            top_k = self._top_k
        if fuzziness is None:
            fuzziness = self._fuzziness
        if scale_score is None:
            scale_score = self._scale_score
        if custom_query is None:
            custom_query = self._custom_query

        docs: List[Document] = []

        try:
            docs = self._document_store._bm25_retrieval(
                query=query,
                filters=filters,
                fuzziness=fuzziness,
                top_k=top_k,
                scale_score=scale_score,
                all_terms_must_match=all_terms_must_match,
                custom_query=custom_query,
            )
        except Exception as e:
            if self._raise_on_failure:
                raise e
            else:
                logger.warning(
                    "An error during BM25 retrieval occurred and will be ignored by returning empty results: %s",
                    str(e),
                    exc_info=True,
                )

        return {"documents": docs}
