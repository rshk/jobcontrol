import copy
import multiprocessing


def test_build_concurrent(jc):
    job_id_1 = jc.storage.create_job(
        'jobcontrol.utils.testing:testing_job',
        kwargs=dict(retval='JOB-CONCURRENT-1', sleep=.1))

    job_id_2 = jc.storage.create_job(
        'jobcontrol.utils.testing:testing_job',
        kwargs=dict(retval='JOB-CONCURRENT-2', sleep=.1))

    build_ids = {}

    def build_job(job_id):
        my_jc = copy.deepcopy(jc)
        build_ids[job_id] = my_jc.build_job(job_id)

    proc_1 = multiprocessing.Process(target=build_job, args=(job_id_1,))
    proc_2 = multiprocessing.Process(target=build_job, args=(job_id_2,))

    # Wait for the two processes to end
    proc_1.start()
    proc_2.start()

    proc_1.join()
    proc_2.join()

    # Now we can inspect the builds
