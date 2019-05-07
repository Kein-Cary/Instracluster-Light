import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import handy.scatter as hsc

import astropy.units as U
import astropy.constants as C
from astropy import cosmology as apcy

from dustmaps.sfd import SFDQuery
from extinction_redden import A_wave
from astropy.coordinates import SkyCoord

import h5py
import numpy as np
import pandas as pd
import astropy.wcs as awc
import subprocess as subpro
import astropy.io.ascii as asc
import astropy.io.fits as fits
##
kpc2cm = U.kpc.to(U.cm)
Mpc2pc = U.Mpc.to(U.pc)
Mpc2cm = U.Mpc.to(U.cm)
rad2asec = U.rad.to(U.arcsec)
pc2cm = U.pc.to(U.cm)
Lsun = C.L_sun.value*10**7
# cosmology model
Test_model = apcy.Planck15.clone(H0 = 67.74, Om0 = 0.311)
H0 = Test_model.H0.value
h = H0/100
Omega_m = Test_model.Om0
Omega_lambda = 1.-Omega_m
Omega_k = 1.- (Omega_lambda + Omega_m)

pixel = 0.396 # the pixel size in unit arcsec
z_ref = 0.250 
Da_ref = Test_model.angular_diameter_distance(z_ref).value
Jy = 10**(-23) # (erg/s)/cm^2
f0 = 3631*10**(-23) # zero point in unit (erg/s)/cm^-2

# sample catalog
with h5py.File('/mnt/ddnfs/data_users/cxkttwl/ICL/data/sample_catalog.h5') as f:
	catalogue = np.array(f['a'])
z = catalogue[0]
ra = catalogue[1]
dec = catalogue[2]
d_file = '/mnt/ddnfs/data_users/cxkttwl/ICL/wget_data/'
def mask_B():
	rp_star = 2*1.5/pixel # mask star radius, in unit pixel
	band = ['u', 'g', 'r', 'i', 'z']
	load = '/mnt/ddnfs/data_users/cxkttwl/ICL/data/'
	sfd = SFDQuery()
	A_lambd = np.array([5.155, 3.793, 2.751, 2.086, 1.479])
	l_wave = np.array([3551, 4686, 6166, 7480, 8932])
	for q in range(2):
		mask = load + 'mask_catalog/source_SQL_Z%.3f_ra%.3f_dec%.3f.txt'%(z[q], ra[q], dec[q])
		cat = pd.read_csv(mask, skiprows = 1)
		ra_s = np.array(cat['ra'])
		dec_s = np.array(cat['dec'])
		mag = np.array(cat['r'])
		R0 = np.array(cat['petroR90_r'])
		'''
		iu = R0 >= 0
		R = 2*R0[iu]/pixel
		Ra = ra_s[iu]
		Dec = dec_s[iu]
		Mag = mag[iu]
		'''
		for p in range(len(band)):
			file = d_file + 'frame-%s-ra%.3f-dec%.3f-redshift%.3f.fits.bz2'%(band[p], ra[q], dec[q], z[q])
			ra_g = ra[q]
			dec_g = dec[q]
			pos = SkyCoord(ra_g, dec_g, frame = 'fk5', unit = 'deg')
			BEV = sfd(pos)
			print('E(B-V) = ', BEV)
			Al = A_wave(l_wave[p], 3.1, A_lambd[p], BEV)

			data_f = fits.open(file)
			img = data_f[0].data
			# extinction correct
			img = img*10**(Al / 2.5)

			head_inf = data_f[0].header
			wcs = awc.WCS(head_inf)
			x_side = data_f[0].data.shape[1]
			y_side = data_f[0].data.shape[0]

			R_ph = rad2asec/(Test_model.angular_diameter_distance(z[q]).value)
			R_p = R_ph/pixel
			cenx, ceny = wcs.all_world2pix(ra_g*U.deg, dec_g*U.deg, 1)

			x, y = wcs.all_world2pix(ra_s*U.deg, dec_s*U.deg, 1)
			ia = (x >= 0) & (x <= x_side)
			ib = (y >= 0) & (y <= y_side)
			ie = (mag <= 20)
			ic = ia & ib & ie
			comx = x[ic]
			comy = y[ic]
			cr = R0[ic]

			Numb = len(cr)
			mask_B = np.ones((img.shape[0], img.shape[1]), dtype = np.float)
			ox = np.linspace(0,2047,2048)
			oy = np.linspace(0,1488,1489)
			basic_coord = np.array(np.meshgrid(ox,oy))
			for k in range(Numb):
				xc = comx[k]
				yc = comy[k]
				idr = np.sqrt((xc - basic_coord[0,:])**2 + 
					(yc - basic_coord[1,:])**2)/rp_star
				jx = idr <= 1
				jx = (-1)*jx+1
				mask_B = mask_B*jx
			
			mirro_B = mask_B*img

			hdu = fits.PrimaryHDU()
			hdu.data = mirro_B
			hdu.header = head_inf
			hdu.writeto(load + 'mask_data/B_plane/B_mask_data_%s_ra%.3f_dec%.3f_z%.3f.fits'%(band[p], ra_g, dec_g, z[q]),overwrite = True)
			# aslo save the mask_matrix
			hdu = fits.PrimaryHDU()
			hdu.data = mask_B
			hdu.header = head_inf
			hdu.writeto(load + 'mask_metrx/mask_B/B_mask_metrx_ra%.3f_dec%.3f_z%.3f.fits'%(ra_g, dec_g, z[q]),overwrite = True)
		print(q/len(z))

	return

def mask_A():
	band_add = ['r', 'i', 'z']
	band_fil = ['u', 'g', 'r', 'i', 'z']
	load = '/mnt/ddnfs/data_users/cxkttwl/ICL/data/'

	param_A = 'default_mask_A.sex'
	param_B = 'default_mask_B.sex'
	out_cat = 'default_mask_A.param'
	out_load_A = './result/mask_A_test.cat'
	out_load_B = './result/mask_B_test.cat'

	rp_star = 2*1.5/pixel
	sfd = SFDQuery()
	A_lambd = np.array([5.155, 3.793, 2.751, 2.086, 1.479])
	l_wave = np.array([3551, 4686, 6166, 7480, 8932])

	N_source = np.zeros(len(z), dtype = np.float)
	bad_record = []
	for q in range(2):

		for l in range(len(band_fil)):

			pro_f = d_file + 'frame-%s-ra%.3f-dec%.3f-redshift%.3f.fits.bz2'%(band_fil[l], ra[q], dec[q], z[q])
			ra_g = ra[q]
			dec_g = dec[q]
			pos = SkyCoord(ra_g, dec_g, frame = 'fk5', unit = 'deg')
			BEV = sfd(pos)
			print('E(B-V) = ', BEV)
			Al = A_wave(l_wave[l], 3.1, A_lambd[l], BEV)

			data_f = fits.open(pro_f)
			img = data_f[0].data
			# extinction correct
			img = img*10**(Al / 2.5)

			head_inf = data_f[0].header
			wcs = awc.WCS(head_inf)
			cx_BCG, cy_BCG = wcs.all_world2pix(ra_g*U.deg, dec_g*U.deg, 1)
			R_ph = rad2asec/(Test_model.angular_diameter_distance(z[q]).value)
			R_p = R_ph/pixel

			combine = np.zeros((1489, 2048), dtype = np.float)
			for p in range(len(band_add)):
				file_p = d_file + 'frame-%s-ra%.3f-dec%.3f-redshift%.3f.fits.bz2'%(band_add[p], ra[q], dec[q], z[q])
				data_p = fits.open(file_p)
				img_p = data_p[0].data
				combine = combine + img_p
			hdu = fits.PrimaryHDU()
			hdu.data = combine
			hdu.header = head_inf
			hdu.writeto('combine_data.fits', overwrite = True)

			#for k in range(len(band_fil)):
			file_source = './combine_data.fits'
			cmd = 'sex '+ file_source + ' -c %s -CATALOG_NAME %s -PARAMETERS_NAME %s'%(param_A, out_load_A, out_cat)
			print(cmd)
			a = subpro.Popen(cmd, shell = True)
			a.wait()

			source = asc.read(out_load_A)
			Numb = np.array(source['NUMBER'][-1])
			N_source[q] = Numb
			A = np.array(source['A_IMAGE'])
			B = np.array(source['B_IMAGE'])
			theta = np.array(source['THETA_IMAGE'])
			cx = np.array(source['X_IMAGE']) - 1
			cy = np.array(source['Y_IMAGE']) - 1
			p_type = np.array(source['CLASS_STAR'])
			#Kron = source['KRON_RADIUS']
			Kron = 5
			a = Kron*A
			b = Kron*B

			mask = load + 'mask_catalog/source_SQL_Z%.3f_ra%.3f_dec%.3f.txt'%(z[q], ra[q], dec[q])
			cat = pd.read_csv(mask, skiprows = 1)
			ra_s = np.array(cat['ra'])
			dec_s = np.array(cat['dec'])
			mag = np.array(cat['r'])
			#R0 = np.array(cat['petroR90_r'])
			x_side = img.shape[1]
			y_side = img.shape[0]
			x, y = wcs.all_world2pix(ra_s*U.deg, dec_s*U.deg, 1)
			ia = (x >= 0) & (x <= x_side)
			ib = (y >= 0) & (y <= y_side)
			ie = (mag <= 20)
			ic = ia & ib & ie
			comx = x[ic]
			comy = y[ic]
			comr = np.ones(len(comx), dtype = np.float) * rp_star
			com_chi = np.zeros(len(comx), dtype = np.float)

			cx = np.r_[cx, comx]
			cy = np.r_[cy, comy]
			a = np.r_[a, 2*comr]
			b = np.r_[b, 2*comr]
			theta = np.r_[theta, com_chi]
			Numb = Numb + len(comx)

			mask_A = np.ones((img.shape[0], img.shape[1]), dtype = np.float)
			ox = np.linspace(0,2047,2048)
			oy = np.linspace(0,1488,1489)
			basic_coord = np.array(np.meshgrid(ox,oy))
			major = a/2
			minor = b/2 # set the star mask based on the major and minor radius
			senior = np.sqrt(major**2 - minor**2)
			for k in range(Numb):
				xc = cx[k]
				yc = cy[k]
				dcr = np.sqrt((xc - cx_BCG)**2 +(yc - cy_BCG)**2)
				if dcr < R_p/20 :
					mask_A = mask_A
				else:
					lr = major[k]
					sr = minor[k]
					cr = senior[k]
					chi = theta[k]*np.pi/180
					df1 = lr**2 - cr**2*np.cos(chi)**2
					df2 = lr**2 - cr**2*np.sin(chi)**2
					fr = (basic_coord[0,:] - xc)**2*df1 +(basic_coord[1,:] - yc)**2*df2\
					- cr**2*np.sin(2*chi)*(basic_coord[0,:] - xc)*(basic_coord[1,:] - yc)
					idr = fr/(lr**2*sr**2)
					jx = idr<=1
					jx = (-1)*jx+1
					mask_A = mask_A*jx

			mirro_A = mask_A *img
			test_region = mirro_A[np.int(cy_BCG)-3:np.int(cy_BCG)+4, np.int(cx_BCG)-3:np.int(cx_BCG)+4]
			if np.sum(test_region) <= 0.1:
				print('There is a bad mask at q = %.0f' % q)
				bad_record.append([ra[q], dec[q], z[q]])

			hdu = fits.PrimaryHDU()
			hdu.data = mirro_A
			hdu.header = head_inf
			hdu.writeto(load + 'mask_data/A_plane/A_mask_data_r_ra%.3f_dec%.3f_z%.3f.fits'%(ra_g, dec_g, z[q]),overwrite = True)

			hdu = fits.PrimaryHDU()
			hdu.data = mask_A
			hdu.header = head_inf
			hdu.writeto(load + 'mask_metrx/mask_A/A_mask_metrx_r_ra%.3f_dec%.3f_z%.3f.fits'%(ra_g, dec_g, z[q]),overwrite = True)

			plt.figure()
			plt.imshow(mirro_A, cmap = 'Greys', origin = 'lower', vmin = 1e-3, norm = mpl.colors.LogNorm())
			hsc.ellipses(cx, cy, w = a, h = b, rot = theta, fc = '', ec = 'r', ls = '--', lw = 0.5)
			hsc.circles(comx, comy, s = comr, fc = '', ec = 'b', ls = '-', lw = 0.5)

			hsc.circles(cx_BCG, cy_BCG, s = R_p, fc = '', ec = 'b', )
			hsc.circles(cx_BCG, cy_BCG, s = 1.1*R_p, fc = '', ec = 'b', ls = '--')
			plt.plot(cx_BCG, cy_BCG, 'bo', alpha = 0.5)
			plt.title('$SEX source mask ra%.3f dec%.3f z%.3f$'%(ra[q], dec[q], z[q]))
			plt.xlim(0, 2048)
			plt.ylim(0, 1489)
			plt.savefig('/mnt/ddnfs/data_users/cxkttwl/ICL/fig_cut/region_cut/A_mask_ra%.3f_dec%.3f_z%.3f.png'%(ra[q], dec[q], z[q]), dpi = 300)
			plt.close()
			'''
			mark_B = fits.getdata(load + 'mask_metrx/mask_B/B_mask_metrx_ra%.3f_dec%.3f_z%.3f.fits'%(ra[q], dec[q], z[q]), header = True)
			sum_mark = mask_A *mark_B[0]
			mirro = sum_mark *img

			plt.figure()
			plt.imshow(mirro, cmap = 'Greys', origin = 'lower', norm = mpl.colors.LogNorm())
			hsc.ellipses(cx, cy, w = a, h = b, rot = theta, fc = '', ec = 'r', lw = 0.5)
			hsc.circles(cx_BCG, cy_BCG, s = R_p, fc = '', ec = 'b', )
			hsc.circles(cx_BCG, cy_BCG, s = 1.1*R_p, fc = '', ec = 'b', ls = '--')
			plt.plot(cx_BCG, cy_BCG, 'bo', alpha = 0.5)
			plt.title('$combine mask ra%.3f dec%.3f z%.3f$'%(ra[q], dec[q], z[q]))
			plt.xlim(0, 2048)
			plt.ylim(0, 1489)
			plt.savefig('/mnt/ddnfs/data_users/cxkttwl/ICL/fig_cut/region_cut/sum_mask_ra%.3f_dec%.3f_z%.3f.png'%(ra[q], dec[q], z[q]), dpi = 300)
			plt.close()
			'''
		print(q/len(z))
	with h5py.File('/mnt/ddnfs/data_users/cxkttwl/ICL/data/sex_source_count.h5', 'w') as f:
		f['a'] = np.array(N_source)

	bad_record = np.array(bad_record)
	with h5py.File('/mnt/ddnfs/data_users/cxkttwl/ICL/data/BCG_bad_log.h5', 'w') as f:
		f['a'] = np.array(bad_record)
	with h5py.File('/mnt/ddnfs/data_users/cxkttwl/ICL/data/BCG_bad_log.h5') as f:
		for tt in range(bad_record.shape[0]):
			f['a'][tt,:] = bad_record[tt,:]
	return

def main():
	mask_B()
	mask_A()

if __name__ == "__main__":
	main()