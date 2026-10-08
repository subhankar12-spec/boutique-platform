# Jenkins Recovery

Back up each Jenkins home volume separately to encrypted access-controlled storage. Treat credential material and controller identity keys as sensitive. Restore to isolated controllers with the matching core/plugin lock, disable triggers, confirm job/config integrity, then re-enable agents and trusted credentials deliberately. Never restore release credentials onto the validation controller.
