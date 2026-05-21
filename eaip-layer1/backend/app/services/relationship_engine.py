"""Relationship engine service for auto-generating and managing file relationships."""

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.file import File
from app.models.relationship import Relationship


class RelationshipEngine:
    """Manages auto-generated and manual relationships between files.

    Auto-generated relationships are created based on shared department
    or shared tags. Manual relationships override auto-generated ones
    and are never overwritten during recalculation.

    Key rules:
    - Never overwrite edges where is_manual = True during auto-generation
    - If both department and tag edges exist between the same pair, keep
      only the tag edge (more specific)
    - Manual relationships override auto-generated ones between the same pair
    - Deduplicate: avoid creating duplicate relationships between the same pair
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def recalculate_for_file(self, file_id: int) -> None:
        """Recalculate auto-generated relationships for a specific file.

        Removes existing auto-generated relationships involving this file,
        then regenerates based on department and tag membership.

        Args:
            file_id: The primary key of the file to recalculate for.
        """
        self._remove_auto_relationships_for_file(file_id)
        file = self._get_file(file_id)
        if file is None:
            return
        self._generate_department_relationships(file)
        self._generate_tag_relationships(file)

    def recalculate_all(self) -> None:
        """Recalculate all auto-generated relationships.

        Removes all auto-generated relationships and regenerates them
        for every file in the index.
        """
        self._remove_all_auto_relationships()
        files = self._get_all_files()
        for file in files:
            self._generate_department_relationships(file)
            self._generate_tag_relationships(file)
        self.db.commit()

    def create_manual_relationship(
        self, source_id: int, target_id: int, rel_type: str
    ) -> Relationship:
        """Create or override a relationship with a manual one.

        If an auto-generated relationship exists between the same pair,
        it is removed and replaced with the manual relationship.

        Args:
            source_id: The source file ID.
            target_id: The target file ID.
            rel_type: The relationship type label.

        Returns:
            The created Relationship record.
        """
        # Remove any existing auto-generated relationship between these files
        self._remove_auto_relationship_between(source_id, target_id)
        # Check if a manual relationship already exists between this pair
        existing = self._get_manual_relationship_between(source_id, target_id)
        if existing:
            existing.relationship_type = rel_type
            self.db.commit()
            self.db.refresh(existing)
            return existing
        # Create new manual relationship
        relationship = Relationship(
            source_file_id=source_id,
            target_file_id=target_id,
            relationship_type=rel_type,
            is_manual=True,
        )
        self.db.add(relationship)
        self.db.commit()
        self.db.refresh(relationship)
        return relationship

    def delete_relationship(self, relationship_id: int) -> bool:
        """Delete a relationship by ID.

        Args:
            relationship_id: The primary key of the relationship to delete.

        Returns:
            True if the relationship was found and deleted, False otherwise.
        """
        relationship = (
            self.db.query(Relationship)
            .filter(Relationship.id == relationship_id)
            .first()
        )
        if relationship is None:
            return False
        self.db.delete(relationship)
        self.db.commit()
        return True

    def get_all_relationships(self) -> list[Relationship]:
        """Get all relationships from the database.

        Returns:
            List of all Relationship records.
        """
        return self.db.query(Relationship).all()

    # ─── Private helpers ─────────────────────────────────────────────

    def _get_file(self, file_id: int) -> File | None:
        """Retrieve a file by ID.

        Args:
            file_id: The primary key of the file.

        Returns:
            The File record, or None if not found.
        """
        return self.db.query(File).filter(File.id == file_id).first()

    def _get_all_files(self) -> list[File]:
        """Retrieve all indexed files.

        Returns:
            List of all File records.
        """
        return self.db.query(File).all()

    def _get_files_in_department(self, department: str) -> list[File]:
        """Get all files belonging to a specific department.

        Args:
            department: The department name to filter by.

        Returns:
            List of File records in the given department.
        """
        return self.db.query(File).filter(File.department == department).all()

    def _get_files_with_any_tag(self, tags: list[str]) -> list[File]:
        """Get all files that share at least one tag from the given list.

        Args:
            tags: List of tag strings to match against.

        Returns:
            List of File records that have at least one matching tag.
        """
        all_files = self.db.query(File).filter(File.tags.isnot(None)).all()
        matching = []
        for file in all_files:
            file_tags = file.tags if file.tags else []
            if set(file_tags) & set(tags):
                matching.append(file)
        return matching

    def _has_manual_relationship_between(
        self, file_id_a: int, file_id_b: int
    ) -> bool:
        """Check if a manual relationship exists between two files (either direction).

        Args:
            file_id_a: First file ID.
            file_id_b: Second file ID.

        Returns:
            True if a manual relationship exists between the pair.
        """
        exists = (
            self.db.query(Relationship)
            .filter(
                Relationship.is_manual == True,  # noqa: E712
                or_(
                    and_(
                        Relationship.source_file_id == file_id_a,
                        Relationship.target_file_id == file_id_b,
                    ),
                    and_(
                        Relationship.source_file_id == file_id_b,
                        Relationship.target_file_id == file_id_a,
                    ),
                ),
            )
            .first()
        )
        return exists is not None

    def _get_manual_relationship_between(
        self, source_id: int, target_id: int
    ) -> Relationship | None:
        """Get an existing manual relationship between two files (either direction).

        Args:
            source_id: Source file ID.
            target_id: Target file ID.

        Returns:
            The manual Relationship record if found, else None.
        """
        return (
            self.db.query(Relationship)
            .filter(
                Relationship.is_manual == True,  # noqa: E712
                or_(
                    and_(
                        Relationship.source_file_id == source_id,
                        Relationship.target_file_id == target_id,
                    ),
                    and_(
                        Relationship.source_file_id == target_id,
                        Relationship.target_file_id == source_id,
                    ),
                ),
            )
            .first()
        )

    def _has_auto_relationship_between(
        self, file_id_a: int, file_id_b: int, rel_type: str | None = None
    ) -> bool:
        """Check if an auto-generated relationship exists between two files.

        Args:
            file_id_a: First file ID.
            file_id_b: Second file ID.
            rel_type: Optional relationship type to filter by.

        Returns:
            True if an auto-generated relationship exists between the pair.
        """
        query = self.db.query(Relationship).filter(
            Relationship.is_manual == False,  # noqa: E712
            or_(
                and_(
                    Relationship.source_file_id == file_id_a,
                    Relationship.target_file_id == file_id_b,
                ),
                and_(
                    Relationship.source_file_id == file_id_b,
                    Relationship.target_file_id == file_id_a,
                ),
            ),
        )
        if rel_type is not None:
            query = query.filter(Relationship.relationship_type == rel_type)
        return query.first() is not None

    def _create_auto_relationship(
        self, source_id: int, target_id: int, rel_type: str
    ) -> None:
        """Create an auto-generated relationship if it doesn't already exist.

        Respects the following rules:
        - Skip if a manual relationship exists between the pair
        - Skip if an auto relationship of the same type already exists
        - If creating a tag edge and a department edge exists, remove the
          department edge (tag is more specific)

        Args:
            source_id: Source file ID.
            target_id: Target file ID.
            rel_type: The relationship type ("department" or "tag").
        """
        # Never overwrite manual relationships
        if self._has_manual_relationship_between(source_id, target_id):
            return

        # Skip if same type auto relationship already exists
        if self._has_auto_relationship_between(source_id, target_id, rel_type):
            return

        # If creating a tag edge and a department edge exists, remove department edge
        if rel_type == "tag" and self._has_auto_relationship_between(
            source_id, target_id, "department"
        ):
            self._remove_auto_relationship_between_typed(
                source_id, target_id, "department"
            )

        # If creating a department edge but a tag edge already exists, skip
        # (tag is more specific and takes precedence)
        if rel_type == "department" and self._has_auto_relationship_between(
            source_id, target_id, "tag"
        ):
            return

        relationship = Relationship(
            source_file_id=source_id,
            target_file_id=target_id,
            relationship_type=rel_type,
            is_manual=False,
        )
        self.db.add(relationship)

    def _generate_department_relationships(self, file: File) -> None:
        """Create edges between files in the same department.

        Args:
            file: The File record to generate department relationships for.
        """
        same_dept_files = self._get_files_in_department(file.department)
        for other in same_dept_files:
            if other.id != file.id:
                self._create_auto_relationship(
                    file.id, other.id, "department"
                )

    def _generate_tag_relationships(self, file: File) -> None:
        """Create edges between files sharing at least one tag.

        Args:
            file: The File record to generate tag relationships for.
        """
        if not file.tags:
            return
        files_with_shared_tags = self._get_files_with_any_tag(file.tags)
        for other in files_with_shared_tags:
            if other.id != file.id:
                self._create_auto_relationship(file.id, other.id, "tag")

    def _remove_auto_relationships_for_file(self, file_id: int) -> None:
        """Remove all auto-generated relationships involving a specific file.

        Args:
            file_id: The file ID to remove auto relationships for.
        """
        self.db.query(Relationship).filter(
            Relationship.is_manual == False,  # noqa: E712
            or_(
                Relationship.source_file_id == file_id,
                Relationship.target_file_id == file_id,
            ),
        ).delete(synchronize_session="fetch")

    def _remove_all_auto_relationships(self) -> None:
        """Remove all auto-generated relationships from the database."""
        self.db.query(Relationship).filter(
            Relationship.is_manual == False  # noqa: E712
        ).delete(synchronize_session="fetch")

    def _remove_auto_relationship_between(
        self, source_id: int, target_id: int
    ) -> None:
        """Remove auto-generated relationships between a specific pair.

        Args:
            source_id: First file ID.
            target_id: Second file ID.
        """
        self.db.query(Relationship).filter(
            Relationship.is_manual == False,  # noqa: E712
            or_(
                and_(
                    Relationship.source_file_id == source_id,
                    Relationship.target_file_id == target_id,
                ),
                and_(
                    Relationship.source_file_id == target_id,
                    Relationship.target_file_id == source_id,
                ),
            ),
        ).delete(synchronize_session="fetch")

    def _remove_auto_relationship_between_typed(
        self, source_id: int, target_id: int, rel_type: str
    ) -> None:
        """Remove auto-generated relationships of a specific type between a pair.

        Args:
            source_id: First file ID.
            target_id: Second file ID.
            rel_type: The relationship type to remove.
        """
        self.db.query(Relationship).filter(
            Relationship.is_manual == False,  # noqa: E712
            Relationship.relationship_type == rel_type,
            or_(
                and_(
                    Relationship.source_file_id == source_id,
                    Relationship.target_file_id == target_id,
                ),
                and_(
                    Relationship.source_file_id == target_id,
                    Relationship.target_file_id == source_id,
                ),
            ),
        ).delete(synchronize_session="fetch")
