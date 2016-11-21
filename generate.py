import os
import subprocess

import logging


def run_process(args, log=True):

    logger = logging.getLogger("subprocess")

    if log:
        logger.debug('%s' % args)

    try:
        p = subprocess.Popen(
            args, bufsize=-1, shell=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True)

        (stdoutdata, stderrdata) = p.communicate()

        if p.returncode != 0:
            # for critical things, we always log, even if log==False
            logger.critical('exit status %d' % p.returncode)
            logger.critical(' for command: %s' % args)
            logger.critical('      stderr: %s' % stderrdata)
            logger.critical('      stdout: %s' % stdoutdata)
            raise OSError

        return (stdoutdata, stderrdata)

    except subprocess.CalledProcessError as e:
        logger.critical('exit status %d' % e.returncode)
        logger.critical(' for command: %s' % args)
        logger.critical('  output: %s' % e.output)
        raise

    except ValueError:
        logger.critical('ValueError for %s' % args)
        raise

    except OSError:
        logger.critical('OSError for %s' % args)
        raise

    except KeyboardInterrupt:
        logger.critical('KeyboardInterrupt during %s' % args)
        try:
            p.kill()
        except UnboundLocalError:
            pass

        raise KeyboardInterrupt


def generate_wav(
        gen_dir, file_id_list, sptk_dir, world_dir, do_post_filtering=True,
        mgc_dim=60, fl=1024, sr=16000):

    pf_coef = 1.4
    fw_alpha = 0.58
    co_coef = 511

    sptk_path = {
        'SOPR': sptk_dir + 'sopr',
        'FREQT': sptk_dir + 'freqt',
        'VSTAT': sptk_dir + 'vstat',
        'MGC2SP': sptk_dir + 'mgc2sp',
        'MERGE': sptk_dir + 'merge',
        'BCP': sptk_dir + 'bcp',
        'MC2B': sptk_dir + 'mc2b',
        'C2ACR': sptk_dir + 'c2acr',
        'MLPG': sptk_dir + 'mlpg',
        'VOPR': sptk_dir + 'vopr',
        'B2MC': sptk_dir + 'b2mc',
        'X2X': sptk_dir + 'x2x',
        'VSUM': sptk_dir + 'vsum'}

    world_path = {
        'ANALYSIS': world_dir + 'analysis',
        'SYNTHESIS': world_dir + 'synth'}

    fw_coef = fw_alpha
    fl_coef = fl

    for filename in file_id_list:
        base = filename

        files = {'sp': base + '.sp',
                 'mgc': base + '.mgc',
                 'f0': base + '.f0',
                 'lf0': base + '.lf0',
                 'ap': base + '.ap',
                 'bap': base + '.bap',
                 'wav': base + '.wav'}

        mgc_file_name = files['mgc']

        cur_dir = os.getcwd()
        os.chdir(gen_dir)

        #  post-filtering
        if do_post_filtering:
            line = "echo 1 1 "
            for i in range(2, mgc_dim):
                line = line + str(pf_coef) + " "

            run_process(
                '{line} | {x2x} +af > {weight}'
                .format(
                    line=line, x2x=sptk_path['X2X'],
                    weight=os.path.join(gen_dir, 'weight')))

            run_process(
                '{freqt} -m {order} -a {fw} -M {co} -A 0 < {mgc} | '
                '{c2acr} -m {co} -M 0 -l {fl} > {base_r0}'
                .format(
                    freqt=sptk_path['FREQT'], order=mgc_dim - 1,
                    fw=fw_coef, co=co_coef, mgc=files['mgc'],
                    c2acr=sptk_path['C2ACR'], fl=fl_coef,
                    base_r0=files['mgc'] + '_r0'))

            run_process(
                '{vopr} -m -n {order} < {mgc} {weight} | '
                '{freqt} -m {order} -a {fw} -M {co} -A 0 | '
                '{c2acr} -m {co} -M 0 -l {fl} > {base_p_r0}'
                .format(
                    vopr=sptk_path['VOPR'], order=mgc_dim - 1,
                    mgc=files['mgc'],
                    weight=os.path.join(gen_dir, 'weight'),
                    freqt=sptk_path['FREQT'], fw=fw_coef, co=co_coef,
                    c2acr=sptk_path['C2ACR'], fl=fl_coef,
                    base_p_r0=files['mgc'] + '_p_r0'))

            run_process(
                '{vopr} -m -n {order} < {mgc} {weight} | '
                '{mc2b} -m {order} -a {fw} | '
                '{bcp} -n {order} -s 0 -e 0 > {base_b0}'
                .format(
                    vopr=sptk_path['VOPR'], order=mgc_dim - 1,
                    mgc=files['mgc'],
                    weight=os.path.join(gen_dir, 'weight'),
                    mc2b=sptk_path['MC2B'], fw=fw_coef,
                    bcp=sptk_path['BCP'], base_b0=files['mgc'] + '_b0'))

            run_process(
                '{vopr} -d < {base_r0} {base_p_r0} | '
                '{sopr} -LN -d 2 | {vopr} -a {base_b0} > {base_p_b0}'
                .format(
                    vopr=sptk_path['VOPR'],
                    base_r0=files['mgc'] + '_r0',
                    base_p_r0=files['mgc'] + '_p_r0',
                    sopr=sptk_path['SOPR'],
                    base_b0=files['mgc'] + '_b0',
                    base_p_b0=files['mgc'] + '_p_b0'))

            run_process(
                '{vopr} -m -n {order} < {mgc} {weight} | '
                '{mc2b} -m {order} -a {fw} | '
                '{bcp} -n {order} -s 1 -e {order} | '
                '{merge} -n {order2} -s 0 -N 0 {base_p_b0} | '
                '{b2mc} -m {order} -a {fw} > {base_p_mgc}'
                .format(
                    vopr=sptk_path['VOPR'], order=mgc_dim - 1,
                    mgc=files['mgc'],
                    weight=os.path.join(gen_dir, 'weight'),
                    mc2b=sptk_path['MC2B'], fw=fw_coef,
                    bcp=sptk_path['BCP'],
                    merge=sptk_path['MERGE'], order2=mgc_dim - 2,
                    base_p_b0=files['mgc'] + '_p_b0',
                    b2mc=sptk_path['B2MC'],
                    base_p_mgc=files['mgc'] + '_p_mgc'))

            mgc_file_name = files['mgc'] + '_p_mgc'

        # Vocoder WORLD

        run_process(
            '{sopr} -magic -1.0E+10 -EXP -MAGIC 0.0 {lf0} | '
            '{x2x} +fd > {f0}'
            .format(
                sopr=sptk_path['SOPR'], lf0=files['lf0'],
                x2x=sptk_path['X2X'], f0=files['f0']))

        run_process(
            '{sopr} -c 0 {bap} | {x2x} +fd > {ap}'.format(
                sopr=sptk_path['SOPR'], bap=files['bap'],
                x2x=sptk_path['X2X'], ap=files['ap']))

        run_process(
            '{mgc2sp} -a {alpha} -g 0 -m {order} -l {fl} -o 2 {mgc} | '
            '{sopr} -d 32768.0 -P | {x2x} +fd > {sp}'.format(
                mgc2sp=sptk_path['MGC2SP'], alpha=fw_alpha,
                order=mgc_dim - 1, fl=fl, mgc=mgc_file_name,
                sopr=sptk_path['SOPR'], x2x=sptk_path['X2X'], sp=files['sp']))

        run_process(
            '{synworld} {fl} {sr} {f0} {sp} {ap} {wav}'.format(
                synworld=world_path['SYNTHESIS'], fl=fl, sr=sr,
                f0=files['f0'], sp=files['sp'], ap=files['ap'],
                wav=files['wav']))

        run_process(
            'rm -f {ap} {sp} {f0} {bap} {lf0} {mgc} {mgc}_b0 {mgc}_p_b0 '
            '{mgc}_p_mgc {mgc}_p_r0 {mgc}_r0 {cmp}'.format(
                ap=files['ap'], sp=files['sp'], f0=files['f0'],
                bap=files['bap'], lf0=files['lf0'], mgc=files['mgc'],
                cmp=base + '.cmp'))
        os.chdir(cur_dir)
